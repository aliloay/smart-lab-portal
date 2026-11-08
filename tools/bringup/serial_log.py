"""
Bring-up serial logger: everything a node prints, saved with the laptop's
clock, while you can still type commands to the node.

    py serial_log.py --list                 which COM ports exist
    py serial_log.py COM5                   log COM5 at 115200 baud
    py serial_log.py COM5 --tag loadcell-noise-1

Writes two files in tools/bringup/logs/ (created on first use):
    <date>_<time>_<tag>.log   every line, prefixed with the laptop time
    <date>_<time>_<tag>.csv   only the node's "CSV,..." lines, as
                              host_iso,host_ms,<the node's fields...>

While it runs:
    a line you type is sent to the node (tare, cal 100, avg 50, stream ...);
    a line starting with "#" is NOT sent: it is written to both files as a
    NOTE row, e.g. "# ref 100.0" before "avg 50" - loadcell_stats.py pairs
    each avg with the latest "# ref <grams>" note;
    Ctrl+C stops (the files are flushed line by line, nothing is lost).

Only what the node actually printed is saved; nothing is added or smoothed.
Close the Arduino Serial Monitor first: one program per COM port.
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys
import threading
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    sys.exit("pyserial is missing: py -m pip install pyserial")

HERE = pathlib.Path(__file__).resolve().parent


def now():
    t = time.time()
    return dt.datetime.fromtimestamp(t).isoformat(timespec="milliseconds"), int(t * 1000)


def main() -> None:
    ap = argparse.ArgumentParser(description="Smart Lab bring-up serial logger")
    ap.add_argument("port", nargs="?", help="e.g. COM5")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--tag", default="", help="short name for the test, used in the file names")
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    args = ap.parse_args()

    if args.list or not args.port:
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports. Plug the ESP32 in by USB (a data cable, not a charge-only one).")
        for p in ports:
            print(f"{p.device:8s} {p.description}")
        return

    logs = HERE / "logs"
    logs.mkdir(exist_ok=True)
    stem = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S") + (f"_{args.tag}" if args.tag else "")
    log_f = open(logs / f"{stem}.log", "a", encoding="utf-8", buffering=1)
    csv_f = open(logs / f"{stem}.csv", "a", encoding="utf-8", buffering=1)
    print(f"Logging {args.port} at {args.baud} baud -> {logs / stem}.log / .csv")
    print('Type a command for the node, "# note" for a note, Ctrl+C to stop.\n')

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.2)
    except serial.SerialException as e:
        sys.exit(f"Cannot open {args.port}: {e}\n(Is the Arduino Serial Monitor still open?)")

    lock = threading.Lock()

    def write_note(text: str) -> None:
        iso, ms = now()
        with lock:
            log_f.write(f"{iso} NOTE {text}\n")
            csv_f.write(f"{iso},{ms},NOTE,{text}\n")

    def keyboard() -> None:
        for line in sys.stdin:
            line = line.rstrip("\r\n")
            if not line:
                continue
            if line.startswith("#"):
                write_note(line[1:].strip())
                print(f"  (note saved: {line[1:].strip()})")
            else:
                with lock:
                    ser.write((line + "\n").encode())
                write_note(f"sent: {line}")

    threading.Thread(target=keyboard, daemon=True).start()
    buf = b""
    try:
        while True:
            chunk = ser.read(256)
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                line = raw.decode("utf-8", "replace").rstrip("\r")
                iso, ms = now()
                print(line)
                with lock:
                    log_f.write(f"{iso} {line}\n")
                    if line.startswith("CSV,"):
                        csv_f.write(f"{iso},{ms},{line[4:]}\n")
    except KeyboardInterrupt:
        print("\nStopped.")
    except serial.SerialException as e:
        print(f"\nSerial port lost: {e}")
        write_note(f"serial port lost: {e}")
    finally:
        ser.close()
        log_f.close()
        csv_f.close()


if __name__ == "__main__":
    main()
