"""Backfill one month of dummy utility telemetry for active devices.

This is purely for demo/billing purposes so that the Utility -> Billing
screen has historical data to work with.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

# When running inside the backend container, /app is on PYTHONPATH,
# so we can import the same modules the API uses.
from database import SessionLocal
from models import Device, DeviceType, TelemetryLatest, TelemetryTimeseries


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_active_devices(db: Session) -> list[Device]:
    """Return devices that are currently 'active' based on TelemetryLatest."""
    cutoff = _now_utc() - timedelta(seconds=90)
    return (
        db.query(Device)
        .join(TelemetryLatest, TelemetryLatest.device_id == Device.id)
        .filter(TelemetryLatest.updated_at >= cutoff)
        .all()
    )


def _classify_utility_mapping(device_type: DeviceType) -> list[tuple[str, str]]:
    """Return list of (utility_kind, index_key) mappings for a device type.

    We mirror the logic in routers.utility._resolve_index_key but avoid importing
    FastAPI/HTTPException here.
    """
    mappings: list[tuple[str, str]] = []
    dt_name = device_type.name if device_type else ""

    # Electricity meters
    if "Comcore AMI" in dt_name:
        mappings.append(("electricity", "total_active_energy"))
    if "Comcore DLMS" in dt_name:
        mappings.append(("electricity", "active_energy_import_total"))

    # Gas (LPG meters)
    if "LPG Meter" in dt_name:
        mappings.append(("gas", "level"))

    # Water: none yet

    return mappings


def _generate_values(
    utility_kind: str,
) -> tuple[float, float]:
    """Generate a start and end index for the month window."""
    if utility_kind == "electricity":
        # kWh index, steadily increasing
        start = 1000.0
        end = start + 150.0
        return start, end
    if utility_kind == "gas":
        # Simple increasing index for demo so consumption > 0
        start = 10.0
        end = start + 40.0
        return start, end
    if utility_kind == "water":
        start = 0.0
        end = 10.0
        return start, end
    return 0.0, 0.0


def backfill_month(db: Session) -> None:
    now = _now_utc()
    start_ts = now - timedelta(days=30)
    end_ts = now

    devices = _get_active_devices(db)
    print(f"Found {len(devices)} active devices to backfill")

    created_count = 0

    for device in devices:
        mappings = _classify_utility_mapping(device.device_type)
        if not mappings:
            # Device not relevant for utility billing
            continue

        for utility_kind, index_key in mappings:
            start_val, end_val = _generate_values(utility_kind)

            db.add(
                TelemetryTimeseries(
                    device_id=device.id,
                    ts=start_ts,
                    key=index_key,
                    value=start_val,
                )
            )
            db.add(
                TelemetryTimeseries(
                    device_id=device.id,
                    ts=end_ts,
                    key=index_key,
                    value=end_val,
                )
            )
            created_count += 2
            print(
                f"Backfilled {utility_kind} index '{index_key}' for device "
                f"{device.device_id}: {start_val} -> {end_val}"
            )

    db.commit()
    print(f"Backfill complete. Created {created_count} TelemetryTimeseries rows.")


def main() -> None:
    db = SessionLocal()
    try:
        backfill_month(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()


