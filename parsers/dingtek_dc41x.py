"""Parser for Dingtek DC41X hexadecimal TCP telemetry frames."""

from dataclasses import dataclass
from typing import Dict, Tuple, Any
import struct
import logging


logger = logging.getLogger(__name__)


class DingtekParseError(Exception):
    """Raised when a Dingtek DC41X frame cannot be parsed."""


@dataclass
class DingtekFrame:
    """Structured representation of a parsed Dingtek frame."""

    device_id: str
    forced_bit: int
    device_type: int
    report_type: int
    packet_size: int
    payload_bytes: bytes
    telemetry: Dict[str, Any]
    raw_hex: str

    @property
    def report_type_label(self) -> str:
        mapping = {
            0x01: "active_report",
            0x02: "periodic_report",
            0x03: "downlink_reply",
        }
        return mapping.get(self.report_type, f"unknown_{self.report_type}")


class DingtekDC41XParser:
    """Parses Dingtek DC41X TCP frames into structured telemetry."""

    PACKET_HEAD = 0x80
    PACKET_TAIL = 0x81

    def parse(self, data: bytes) -> DingtekFrame:
        """Parse a raw TCP frame."""
        if len(data) < 6:
            raise DingtekParseError("Frame too short")

        if data[0] != self.PACKET_HEAD or data[-1] != self.PACKET_TAIL:
            raise DingtekParseError("Invalid packet delimiters")

        forced_bit = data[1]
        device_type = data[2]
        report_type = data[3]
        packet_size = data[4]
        payload = data[5:-1]  # Exclude tail

        if report_type not in (0x01, 0x02):
            raise DingtekParseError(f"Unsupported report type {report_type:#04x}")

        telemetry, device_id = self._parse_payload_type_one(payload)

        return DingtekFrame(
            device_id=device_id,
            forced_bit=forced_bit,
            device_type=device_type,
            report_type=report_type,
            packet_size=packet_size,
            payload_bytes=payload,
            telemetry=telemetry,
            raw_hex=data.hex().upper(),
        )

    def _parse_payload_type_one(self, payload: bytes) -> Tuple[Dict[str, Any], str]:
        """Parse data type 0x01/0x02 payloads."""
        cursor = 0

        def read_bytes(length: int) -> bytes:
            nonlocal cursor
            if cursor + length > len(payload):
                raise DingtekParseError("Unexpected end of payload")
            chunk = payload[cursor:cursor + length]
            cursor += length
            return chunk

        telemetry: Dict[str, Any] = {}

        height_bytes = read_bytes(2)
        telemetry["height_mm"] = int.from_bytes(height_bytes, "big")

        gps_selection = read_bytes(1)[0]
        telemetry["gps_present"] = gps_selection == 0x01

        if telemetry["gps_present"]:
            longitude_bytes = read_bytes(4)
            latitude_bytes = read_bytes(4)
            telemetry["longitude_deg"] = self._le_float(longitude_bytes)
            telemetry["latitude_deg"] = self._le_float(latitude_bytes)
        else:
            telemetry["longitude_deg"] = None
            telemetry["latitude_deg"] = None

        telemetry["temperature_c"] = self._signed_byte(read_bytes(1)[0])
        telemetry["reserved"] = read_bytes(1)[0]
        telemetry["angle_deg"] = read_bytes(1)[0]

        status_bytes = read_bytes(2)
        status_high = status_bytes[0]
        status_low = status_bytes[1]

        full_alarm_code = (status_high & 0xF0) >> 4
        move_alarm_code = (status_low & 0xF0) >> 4
        power_alarm_code = status_low & 0x0F

        telemetry["full_alarm"] = full_alarm_code == 0x01
        telemetry["move_alarm"] = move_alarm_code == 0x01
        telemetry["battery_low_alarm"] = power_alarm_code == 0x01
        telemetry["status_bytes"] = status_bytes.hex().upper()

        battery_bytes = read_bytes(2)
        battery_mv = int.from_bytes(battery_bytes, "big")
        telemetry["battery_mv"] = battery_mv
        telemetry["battery_v"] = round(battery_mv / 1000, 3)

        rsrp_bytes = read_bytes(4)
        telemetry["rsrp_dbm"] = round(self._le_float(rsrp_bytes), 2)

        frame_counter = int.from_bytes(read_bytes(2), "big")
        telemetry["frame_counter"] = frame_counter

        device_id_bytes = read_bytes(8)
        device_id = self._bcd_to_string(device_id_bytes)
        telemetry["device_id_bcd"] = device_id

        if cursor != len(payload):
            leftover = payload[cursor:].hex()
            logger.debug("Unparsed payload remainder: %s", leftover)

        return telemetry, device_id

    @staticmethod
    def _signed_byte(value: int) -> int:
        """Decode signed 8-bit integer."""
        return value - 256 if value > 127 else value

    @staticmethod
    def _le_float(raw: bytes) -> float:
        """Decode little-endian IEEE-754 float."""
        if len(raw) != 4:
            raise DingtekParseError("Float field must be 4 bytes")
        return struct.unpack("<f", raw)[0]

    @staticmethod
    def _bcd_to_string(raw: bytes) -> str:
        """Convert packed BCD bytes to a decimal string."""
        digit_chars = "0123456789ABCDEF"
        digits = []
        for byte in raw:
            high = (byte >> 4) & 0x0F
            low = byte & 0x0F
            digits.append(digit_chars[high])
            digits.append(digit_chars[low])
        return "".join(digits)


__all__ = ["DingtekDC41XParser", "DingtekParseError", "DingtekFrame"]


