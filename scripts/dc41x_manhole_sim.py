#!/usr/bin/env python3
"""
DC41X Smart Manhole NB-IoT TCP simulator for device 1865057042853304.

- Opens a TCP connection to the backend TCP ingestion server.
- Sends a Dingtek DC41X hex frame every ~20 seconds (~3 messages per minute).

This uses the same protocol as the DC41X tank sensor, but with a different
Device ID so it maps to the \"DC41X Smart Manhole 001\" device in the DB.
"""

import os
import socket
import time


TCP_HOST = os.getenv("TCP_HOST", "127.0.0.1")
TCP_PORT = int(os.getenv("TCP_PORT", "6000"))

# Base sample frame from documentation but with the last byte of Device ID
# changed from 0x03 to 0x04 so the parsed device_id becomes 1865057042853304.
BASE_FRAME_HEX = (
    "800001011E04E20019012500100168008064C40002"
    "1865057042853304"
    "81"
)


def send_frame():
    frame_hex = os.getenv("DC41X_MANHOLE_FRAME_HEX", BASE_FRAME_HEX)
    frame_bytes = bytes.fromhex(frame_hex)

    print(f"Sending DC41X manhole frame ({len(frame_bytes)} bytes) to {TCP_HOST}:{TCP_PORT}")

    with socket.create_connection((TCP_HOST, TCP_PORT), timeout=10) as sock:
        sock.sendall(frame_bytes)
        # Optional: read a response if server sends one
        try:
            sock.settimeout(5)
            resp = sock.recv(4096)
            if resp:
                print("Received response:", resp.decode(errors="replace").strip())
            else:
                print("No response from server (expected for fire-and-forget devices).")
        except socket.timeout:
            print("No response received (timeout).")


def main():
    interval_seconds = 20  # ~3 messages per minute
    print(f"DC41X Smart Manhole simulator connecting to {TCP_HOST}:{TCP_PORT}")
    print(f"Sending frames every {interval_seconds} seconds for device_id=1865057042853304")

    while True:
        try:
            send_frame()
        except Exception as exc:
            print(f"Error sending DC41X manhole frame: {exc}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()


