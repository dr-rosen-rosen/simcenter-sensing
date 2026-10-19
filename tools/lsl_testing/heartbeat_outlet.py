#!/usr/bin/env python3
"""Heartbeat test outlet: validates the LSL loop with zero hardware.

Publishes a marker stream at a fixed rate. Start LabRecorder, confirm the
stream appears in its list, record a short .xdf, then inspect it with
check_xdf.py. Useful any time you need a known-good outlet to test the
LAN, a new machine, or LabRecorder itself.

LSL stream schema:
    name:           simcenter.test.heartbeat (override with --name)
    type:           Markers
    channel_count:  1 (string)
    nominal_srate:  0 (irregular)
    sample format:  "beat=<n>"
"""
import argparse
import socket
import sys
import time

from pylsl import StreamInfo, StreamOutlet


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rate", type=float, default=1.0, help="beats per second (default 1)")
    ap.add_argument("--name", default="simcenter.test.heartbeat")
    args = ap.parse_args()

    info = StreamInfo(args.name, "Markers", 1, 0, "string",
                      f"heartbeat-{socket.gethostname()}")
    outlet = StreamOutlet(info)
    print(f"Publishing {args.name} at {args.rate}/s - Ctrl+C to stop")
    n = 0
    try:
        while True:
            outlet.push_sample([f"beat={n}"])
            n += 1
            time.sleep(1.0 / args.rate)
    except KeyboardInterrupt:
        print(f"\nStopped after {n} beats")
    return 0


if __name__ == "__main__":
    sys.exit(main())
