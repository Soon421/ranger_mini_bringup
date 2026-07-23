#!/usr/bin/env python3
"""
One-shot tool to switch a UM7 IMU to a target UART baud and persist it to flash.

Run while the um7_driver node is NOT running (the script needs exclusive access
to the serial port). Default: switch from 115200 -> 921600 and flash-commit.

Usage:
    python3 um7_set_baud.py --port /dev/ttyUSB0 --from 115200 --to 921600
"""

import argparse
import struct
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not installed. Run: pip install pyserial   (or apt install python3-serial)")


# UM7 firmware register definitions (mirrors um7_firmware_registers.hpp)
CREG_COM_SETTINGS = 0x00
COM_BAUD_START = 28
CHR_GET_FW_VERSION = 0xAA   # COMMAND_START_ADDRESS + 0 = 170
CHR_FLASH_COMMIT   = 0xAB   # COMMAND_START_ADDRESS + 1 = 171

PACKET_HAS_DATA = 1 << 7

BAUD_CODES = {
    9600: 0, 14400: 1, 19200: 2, 38400: 3, 57600: 4,
    115200: 5, 128000: 6, 153600: 7, 230400: 8, 256000: 9,
    460800: 10, 921600: 11,
}


def build_packet(address: int, data: bytes = b"") -> bytes:
    """Build a single-register UM7 packet (not batch). Checksum is uint16 BE sum."""
    if len(data) not in (0, 4):
        raise ValueError("data must be empty or exactly 4 bytes (single register)")
    pt = PACKET_HAS_DATA if data else 0
    body = b"snp" + bytes([pt, address]) + data
    checksum = sum(body) & 0xFFFF
    return body + struct.pack(">H", checksum)


def find_packet(buf: bytes):
    """Locate 'snp' header in buf, return (start_index, type, address, data, end_index) or None."""
    i = buf.find(b"snp")
    if i < 0 or len(buf) < i + 7:
        return None
    pt = buf[i + 3]
    addr = buf[i + 4]
    has_data = bool(pt & PACKET_HAS_DATA)
    is_batch = bool(pt & 0x40)
    dlen = ((pt >> 2) & 0x0F) if is_batch else (1 if has_data else 0)
    end = i + 5 + dlen * 4 + 2
    if len(buf) < end:
        return None
    data = buf[i + 5 : i + 5 + dlen * 4]
    return (i, pt, addr, data, end)


def read_for(ser: serial.Serial, seconds: float) -> bytes:
    """Read whatever is on the port for `seconds` (best-effort, non-strict)."""
    end = time.monotonic() + seconds
    out = b""
    while time.monotonic() < end:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            out += chunk
        else:
            time.sleep(0.01)
    return out


def ping_fw_version(ser: serial.Serial) -> bool:
    """Send GET_FW_VERSION and look for any matching response within 0.5s."""
    ser.reset_input_buffer()
    ser.write(build_packet(CHR_GET_FW_VERSION))
    ser.flush()
    buf = read_for(ser, 0.5)
    # Any 'snp' framed response is enough — UM7 echoes the address byte back.
    while buf:
        found = find_packet(buf)
        if not found:
            return False
        i, pt, addr, data, end = found
        if addr == CHR_GET_FW_VERSION:
            return True
        buf = buf[end:]
    return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", default="/dev/ttyUSB0")
    p.add_argument("--from", dest="from_baud", type=int, default=115200,
                   help="UM7 current baud (default 115200)")
    p.add_argument("--to", dest="to_baud", type=int, default=921600,
                   help="UM7 target baud (default 921600)")
    p.add_argument("--no-flash", action="store_true",
                   help="Skip flash commit (change is volatile, lost on power cycle)")
    args = p.parse_args()

    if args.to_baud not in BAUD_CODES:
        sys.exit(f"Unsupported target baud {args.to_baud}. "
                 f"Allowed: {sorted(BAUD_CODES.keys())}")

    target_code = BAUD_CODES[args.to_baud]
    comm_value = (target_code << COM_BAUD_START) & 0xFFFFFFFF

    print(f"[1/4] Opening {args.port} at {args.from_baud} baud")
    try:
        ser = serial.Serial(args.port, args.from_baud, timeout=0.2)
    except serial.SerialException as e:
        sys.exit(f"Failed to open port: {e}  (is the driver still running?)")

    try:
        # Sanity check: can we talk to UM7 at the assumed baud?
        print(f"[2/4] Pinging UM7 at {args.from_baud}...")
        if not ping_fw_version(ser):
            print("    -> No valid response. Retrying at the target baud "
                  "(in case it was already changed)...")
            ser.baudrate = args.to_baud
            ser.reset_input_buffer()
            if ping_fw_version(ser):
                print(f"    UM7 is already at {args.to_baud}. Nothing to do.")
                return 0
            sys.exit(f"No response at {args.from_baud} or {args.to_baud}. "
                     f"Check cabling and that the driver is stopped.")
        print(f"    UM7 responded at {args.from_baud}.")

        print(f"[3/4] Writing CREG_COM_SETTINGS = 0x{comm_value:08X} "
              f"(BAUD_CODE={target_code} -> {args.to_baud})")
        data = struct.pack(">I", comm_value)
        ser.reset_input_buffer()
        ser.write(build_packet(CREG_COM_SETTINGS, data))
        ser.flush()
        # UM7 ACKs at OLD baud, then switches its UART. Brief grace period.
        time.sleep(0.1)

        # Switch host side to new baud.
        ser.baudrate = args.to_baud
        ser.reset_input_buffer()
        time.sleep(0.05)

        print(f"[4/4] Verifying UM7 at {args.to_baud}...")
        if not ping_fw_version(ser):
            sys.exit("Verification failed: no response at target baud. "
                     "UM7 may be in a weird state; power-cycle and rerun.")
        print(f"    UM7 confirmed at {args.to_baud}.")

        if args.no_flash:
            print("Skipping FLASH_COMMIT (change is volatile, lost on power cycle).")
        else:
            print("Sending CHR_FLASH_COMMIT to persist across power cycles...")
            ser.reset_input_buffer()
            ser.write(build_packet(CHR_FLASH_COMMIT))
            ser.flush()
            # Flash commit can take a moment; UM7 stalls UART during write.
            time.sleep(0.5)
            if not ping_fw_version(ser):
                print("WARN: post-commit ping failed; UM7 may still be busy. "
                      "Power-cycle and re-verify manually.")
            else:
                print("Flash commit done.")

        print(f"\nDONE. UM7 is now at {args.to_baud} baud (persisted to flash).")
        print("You can now launch the driver with `baud: {0}`.".format(args.to_baud))
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    sys.exit(main())
