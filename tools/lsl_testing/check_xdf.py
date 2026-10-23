#!/usr/bin/env python3
"""Inspect an .xdf recording: stream inventory, timing, overlap.

Streams are classified three ways:
- *continuous*: nominal rate > 0 and actually delivering near it
- *sparse*: nominal rate > 0 but delivering far below it (e.g. Tobii's
  SyncInOut declares 10 Hz but fires on change ~0.2 Hz) — excluded from
  the overlap-window computation, reported like event streams
- *irregular*: nominal rate 0 (marker/event streams)

The overlap window is computed across true continuous streams only;
sparse and irregular events are then checked against that window.

Usage:
    python check_xdf.py path/to/session.xdf

Importable: analyze(path) returns a dict; format_report(result) renders
the human-readable report (used by tools/session_orchestrator).
"""
import argparse
import sys

import pyxdf

# A nominally-continuous stream delivering below this fraction of its
# declared rate is treated as sparse/eventful and excluded from the
# overlap-window computation.
SPARSE_FACTOR = 0.5


def _describe(s):
    info = s["info"]
    ts = s["time_stamps"]
    n = len(ts)
    d = {
        "name": info["name"][0],
        "type": info["type"][0],
        "channels": int(info["channel_count"][0]),
        "nominal_hz": float(info["nominal_srate"][0]),
        "n_samples": n,
        "t0": float(ts[0]) if n else None,
        "t1": float(ts[-1]) if n else None,
        "duration": float(ts[-1] - ts[0]) if n > 1 else 0.0,
        "effective_hz": None,
    }
    if n > 1 and d["duration"] > 0:
        d["effective_hz"] = (n - 1) / d["duration"]
    return d


def analyze(path):
    """Load an .xdf and return a structured summary dict."""
    streams, _header = pyxdf.load_xdf(str(path))
    out = {
        "path": str(path),
        "n_streams": len(streams),
        "continuous": [],
        "sparse": [],
        "irregular": [],
        "overlap": None,
        "warnings": [],
    }
    raw = []
    for s in streams:
        d = _describe(s)
        # keep small marker payloads for the report
        if d["nominal_hz"] == 0 and 0 < d["n_samples"] <= 20:
            d["events"] = [
                (float(t), v[0] if len(v) else "")
                for t, v in zip(s["time_stamps"], s["time_series"])
            ]
        raw.append(d)

    for d in raw:
        if d["nominal_hz"] > 0:
            if d["n_samples"] == 0:
                d["flag"] = "EMPTY"
                out["continuous"].append(d)
            elif d["n_samples"] == 1:
                d["flag"] = "single sample"
                out["continuous"].append(d)
            elif (d["effective_hz"] or 0) < SPARSE_FACTOR * d["nominal_hz"]:
                out["sparse"].append(d)
            else:
                out["continuous"].append(d)
        else:
            out["irregular"].append(d)

    spans = [(d["t0"], d["t1"]) for d in out["continuous"] if d["n_samples"] > 1]
    if len(spans) > 1:
        ov0 = max(t0 for t0, _ in spans)
        ov1 = min(t1 for _, t1 in spans)
        if ov1 > ov0:
            out["overlap"] = {"t0": ov0, "t1": ov1, "duration": ov1 - ov0}
        else:
            out["warnings"].append(
                "continuous streams do not overlap in time - check that "
                "all devices were recording simultaneously")
    elif len(spans) == 1:
        out["overlap"] = {"t0": spans[0][0], "t1": spans[0][1],
                          "duration": spans[0][1] - spans[0][0],
                          "single_stream": True}

    if out["overlap"]:
        w0, w1 = out["overlap"]["t0"], out["overlap"]["t1"]
        for d in out["sparse"] + out["irregular"]:
            if d["n_samples"]:
                # events inside the continuous window (approximate for
                # streams where we kept only summary stats)
                if "events" in d:
                    d["inside_window"] = sum(1 for t, _ in d["events"] if w0 <= t <= w1)
                elif d["t0"] is not None:
                    d["inside_window"] = d["n_samples"] if (d["t0"] >= w0 and d["t1"] <= w1) else None
    return out


def format_report(out):
    lines = [f"{out['n_streams']} stream(s) in {out['path']} "
             f"({len(out['continuous'])} continuous, {len(out['sparse'])} sparse, "
             f"{len(out['irregular'])} irregular)", ""]

    lines.append("## Continuous streams")
    for d in out["continuous"]:
        line = (f"- {d['name']} (type={d['type']}, ch={d['channels']}, "
                f"nominal={d['nominal_hz']:g} Hz): {d['n_samples']} samples")
        if d.get("flag"):
            line += f"  [{d['flag']}]"
        elif d["n_samples"] > 1:
            line += f", {d['duration']:.1f}s"
            if d["effective_hz"]:
                line += f", effective {d['effective_hz']:.2f} Hz"
        lines.append(line)

    if out["overlap"]:
        o = out["overlap"]
        if o.get("single_stream"):
            lines.append(f"\nOnly one continuous stream; its span: {o['duration']:.1f}s")
        else:
            lines.append(f"\nContinuous-stream overlap window: {o['duration']:.1f}s "
                         f"({o['t0']:.1f} .. {o['t1']:.1f})")
    for w in out["warnings"]:
        lines.append(f"\nWARNING: {w}")

    if out["sparse"]:
        lines.append("\n## Sparse streams (declared continuous, delivering far below "
                     "nominal - excluded from overlap window)")
        for d in out["sparse"]:
            line = (f"- {d['name']} (type={d['type']}, nominal={d['nominal_hz']:g} Hz, "
                    f"effective {d['effective_hz']:.2f} Hz): {d['n_samples']} samples")
            if d.get("inside_window") is not None:
                line += f", {d['inside_window']}/{d['n_samples']} inside the overlap window"
            lines.append(line)

    lines.append("\n## Irregular / marker streams")
    for d in out["irregular"]:
        line = f"- {d['name']} (type={d['type']}): {d['n_samples']} event(s)"
        if d.get("inside_window") is not None:
            line += f", {d['inside_window']}/{d['n_samples']} inside the overlap window"
        lines.append(line)
        for t, v in d.get("events", []):
            lines.append(f"    {t:.3f}  {v}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("xdf", help="path to .xdf file from LabRecorder")
    args = ap.parse_args()
    print(format_report(analyze(args.xdf)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
