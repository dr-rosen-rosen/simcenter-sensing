#!/usr/bin/env python3
"""Inspect an .xdf recording: stream inventory, timing, overlap.

Run after every validation recording. Prints each stream's name, type,
channel count, sample count, duration, and effective rate; dumps the
contents of small marker streams; and reports the common time window
shared by all streams (the thing that actually matters for alignment).

Usage:
    python check_xdf.py path/to/session.xdf
"""
import argparse
import sys

import pyxdf


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("xdf", help="path to .xdf file from LabRecorder")
    args = ap.parse_args()

    streams, _header = pyxdf.load_xdf(args.xdf)
    if not streams:
        sys.exit("No streams in file")

    print(f"{len(streams)} stream(s) in {args.xdf}\n")
    starts, ends = [], []
    for s in streams:
        info = s["info"]
        name = info["name"][0]
        stype = info["type"][0]
        nch = info["channel_count"][0]
        nominal = float(info["nominal_srate"][0])
        ts = s["time_stamps"]
        n = len(ts)
        line = f"- {name} (type={stype}, ch={nch}, nominal={nominal:g} Hz): {n} samples"
        if n:
            t0, t1 = ts[0], ts[-1]
            starts.append(t0)
            ends.append(t1)
            line += f", {t1 - t0:.1f}s"
            if n > 1 and nominal > 0 and t1 > t0:
                line += f", effective {(n - 1) / (t1 - t0):.2f} Hz"
        print(line)
        if stype == "Markers" and 0 < n <= 20:
            for t, v in zip(ts, s["time_series"]):
                print(f"    {t:.3f}  {v[0] if len(v) else ''}")

    if len(starts) > 1:
        ov0, ov1 = max(starts), min(ends)
        if ov1 > ov0:
            print(f"\nCommon overlap window across all streams: {ov1 - ov0:.1f}s")
        else:
            print("\nWARNING: streams do not overlap in time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
