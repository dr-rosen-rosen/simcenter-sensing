#!/usr/bin/env python3
"""Synthetic device simulator: fake LSL streams for orchestrator testing.

Publishes a representative subset of the real lab's streams so the
orchestrator (preflight, recording, verification) can be developed and
tested with no hardware:

    EmotiBit-like:  PPG_IR / PPG_RED / PPG_GRN @ 25 Hz, EDA @ 15 Hz,
                    TEMP1 @ 7.5 Hz, ACC_X/Y/Z @ 25 Hz, HR events ~1/s
    Tobii-like:     Gaze2d (2ch) @ 50 Hz
    Mic bridge:     simcenter.mic.marker, 1 marker/s
    ZedBox bridge:  simcenter.zed.SIM0001, 1 marker/s

Failure injection for testing preflight:
    --drop NAME   do not start that stream (simulates a dead device)
    --dup NAME    start that stream twice (simulates a stale duplicate
                  connector, as happened with G3LSLConnector 2026-10-21)

Usage:
    python simulate_devices.py
    python simulate_devices.py --drop PPG_IR --dup Gaze2d
"""
import argparse
import math
import os
import random
import sys
import threading
import time

# macOS: point pylsl at the locally staged liblsl if not already set
if sys.platform == "darwin" and "PYLSL_LIB" not in os.environ:
    _local = os.path.expanduser("~/.local/lib/liblsl.dylib")
    if os.path.exists(_local):
        os.environ["PYLSL_LIB"] = _local

from pylsl import StreamInfo, StreamOutlet  # noqa: E402

STOP = threading.Event()

CONTINUOUS = [
    # (name, type, channels, rate_hz)
    ("PPG_IR", "PPGInfrared", 1, 25.0),
    ("PPG_RED", "PPGRed", 1, 25.0),
    ("PPG_GRN", "PPGGreen", 1, 25.0),
    ("EDA", "EDA", 1, 15.0),
    ("TEMP1", "Temperature", 1, 7.5),
    ("ACC_X", "AccelerometerX", 1, 25.0),
    ("ACC_Y", "AccelerometerY", 1, 25.0),
    ("ACC_Z", "AccelerometerZ", 1, 25.0),
    ("Gaze2d", "Gaze2d", 2, 50.0),
]

MARKERS = [
    # (name, type, interval_s, payload_fn)
    ("simcenter.mic.marker", "Markers", 1.0,
     lambda n: f"frames={n * 16000} sr=16000"),
    ("simcenter.zed.SIM0001", "Markers", 1.0,
     lambda n: f"serial=SIM0001 frame={n * 30} cam_ts_ns={n * 33000000}"),
    ("HR", "HeartRate", 1.0, lambda n: f"{60 + random.randint(-5, 5)}"),
]


def run_continuous(name, stype, nch, rate, instance=0):
    source_id = f"sim-{name}-{instance}"
    info = StreamInfo(name, stype, nch, rate, "float32", source_id)
    outlet = StreamOutlet(info)
    period = 1.0 / rate
    t0 = time.monotonic()
    i = 0
    while not STOP.is_set():
        val = math.sin(2 * math.pi * 0.2 * (time.monotonic() - t0))
        outlet.push_sample([val + random.gauss(0, 0.05)] * nch)
        i += 1
        target = t0 + i * period
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)


def run_marker(name, stype, interval, payload_fn, instance=0):
    source_id = f"sim-{name}-{instance}"
    info = StreamInfo(name, stype, 1, 0, "string", source_id)
    outlet = StreamOutlet(info)
    n = 0
    while not STOP.is_set():
        outlet.push_sample([payload_fn(n)])
        n += 1
        time.sleep(interval)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drop", action="append", default=[],
                    help="stream name to NOT start (repeatable)")
    ap.add_argument("--dup", action="append", default=[],
                    help="stream name to start twice (repeatable)")
    args = ap.parse_args()

    threads = []
    started = []
    for name, stype, nch, rate in CONTINUOUS:
        if name in args.drop:
            continue
        copies = 2 if name in args.dup else 1
        for inst in range(copies):
            t = threading.Thread(target=run_continuous,
                                 args=(name, stype, nch, rate, inst), daemon=True)
            t.start()
            threads.append(t)
            started.append(name + ("" if copies == 1 else f" [dup {inst}]"))
    for name, stype, interval, fn in MARKERS:
        if name in args.drop:
            continue
        copies = 2 if name in args.dup else 1
        for inst in range(copies):
            t = threading.Thread(target=run_marker,
                                 args=(name, stype, interval, fn, inst), daemon=True)
            t.start()
            threads.append(t)
            started.append(name + ("" if copies == 1 else f" [dup {inst}]"))

    print(f"Simulating {len(started)} outlet(s):")
    for s in started:
        print(f"  {s}")
    if args.drop:
        print(f"Dropped (simulated dead): {', '.join(args.drop)}")
    print("Ctrl+C to stop")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        STOP.set()
        print("\nStopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
