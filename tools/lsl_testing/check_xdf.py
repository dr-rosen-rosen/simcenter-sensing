#!/usr/bin/env python3
"""Inspect an .xdf recording: stream inventory, timing, overlap.

Run after every validation recording. Streams are split into *continuous*
(nominal rate > 0: physio, audio markers at fixed cadence, etc.) and
*irregular* (nominal rate 0: marker/event streams, which only carry
timestamps when something happens). The overlap check that matters is
across continuous streams; irregular events are then checked against
that window rather than penalizing it.

Usage:
    python check_xdf.py path/to/session.xdf
"""
import argparse
import sys

import pyxdf


def describe(s):
    info = s["info"]
    name = info["name"][0]
    stype = info["type"][0]
    nch = info["channel_count"][0]
    nominal = float(info["nominal_srate"][0])
    ts = s["time_stamps"]
    return name, stype, nch, nominal, ts


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("xdf", help="path to .xdf file from LabRecorder")
    args = ap.parse_args()

    streams, _header = pyxdf.load_xdf(args.xdf)
    if not streams:
        sys.exit("No streams in file")

    continuous, irregular = [], []
    for s in streams:
        (continuous if float(s["info"]["nominal_srate"][0]) > 0 else irregular).append(s)

    print(f"{len(streams)} stream(s) in {args.xdf} "
          f"({len(continuous)} continuous, {len(irregular)} irregular)\n")

    print("## Continuous streams")
    starts, ends = [], []
    for s in continuous:
        name, stype, nch, nominal, ts = describe(s)
        n = len(ts)
        line = f"- {name} (type={stype}, ch={nch}, nominal={nominal:g} Hz): {n} samples"
        if n > 1:
            t0, t1 = ts[0], ts[-1]
            starts.append(t0)
            ends.append(t1)
            line += f", {t1 - t0:.1f}s"
            if t1 > t0:
                line += f", effective {(n - 1) / (t1 - t0):.2f} Hz"
        elif n == 1:
            line += "  [single sample - excluded from overlap]"
        else:
            line += "  [EMPTY]"
        print(line)

    window = None
    if len(starts) > 1:
        ov0, ov1 = max(starts), min(ends)
        if ov1 > ov0:
            window = (ov0, ov1)
            print(f"\nContinuous-stream overlap window: {ov1 - ov0:.1f}s "
                  f"({ov0:.1f} .. {ov1:.1f})")
        else:
            print("\nWARNING: continuous streams do not overlap in time - "
                  "check that all devices were recording simultaneously")
    elif len(starts) == 1:
        window = (starts[0], ends[0])
        print(f"\nOnly one continuous stream; its span: {ends[0] - starts[0]:.1f}s")

    print("\n## Irregular / marker streams")
    for s in irregular:
        name, stype, nch, nominal, ts = describe(s)
        n = len(ts)
        line = f"- {name} (type={stype}): {n} event(s)"
        if n and window:
            inside = sum(1 for t in ts if window[0] <= t <= window[1])
            line += f", {inside}/{n} inside the overlap window"
        print(line)
        if 0 < n <= 20:
            for t, v in zip(ts, s["time_series"]):
                print(f"    {t:.3f}  {v[0] if len(v) else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
