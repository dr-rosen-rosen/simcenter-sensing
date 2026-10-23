#!/usr/bin/env python3
"""Session orchestrator: preflight, record, verify, manifest - one command.

Wraps a data-collection session end to end:

1. PREFLIGHT - resolve LSL streams and check each expected stream is
   present, present EXACTLY the expected number of times (stale duplicate
   connectors produce double streams), and actually FLOWING (LabRecorder
   records checked-but-dead streams as empty tracks without complaint).
2. RECORD - drive LabRecorder via its remote-control socket: refresh,
   select all, set a filename built from the identifiers convention
   (docs/identifiers.md), start.
3. ANNOTATE - while recording, lines typed at the prompt are published as
   LSL markers on `simcenter.orchestrator` (type Markers) and logged.
   Type 'stop' to end the session.
4. VERIFY + MANIFEST - after stop, run the check_xdf analysis on the
   recording and write a session manifest (JSON) beside it.

Usage:
    python orchestrate.py preflight [--profile P]
    python orchestrate.py run --unit T001 [--run 1] [--profile P] [--force]

The profile (TOML) defines expected streams and LabRecorder host/port -
see profiles/default.toml. Nothing here is on the capture-critical path:
if the orchestrator dies mid-session, LabRecorder keeps recording.
"""
import argparse
import datetime as dt
import getpass
import json
import os
import socket
import sys
import time
import tomllib
from pathlib import Path

# macOS: point pylsl at the locally staged liblsl if not already set
if sys.platform == "darwin" and "PYLSL_LIB" not in os.environ:
    _local = os.path.expanduser("~/.local/lib/liblsl.dylib")
    if os.path.exists(_local):
        os.environ["PYLSL_LIB"] = _local

from pylsl import StreamInfo, StreamInlet, StreamOutlet, local_clock, resolve_streams  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lsl_testing"))
import check_xdf  # noqa: E402


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

def load_profile(path):
    with open(path, "rb") as f:
        prof = tomllib.load(f)
    prof.setdefault("preflight", {})
    prof["preflight"].setdefault("resolve_seconds", 3.0)
    prof["preflight"].setdefault("flow_seconds", 3.0)
    return prof


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

def preflight(prof):
    """Check expected streams: present, exactly-once, flowing.

    Returns (ok: bool, results: list of dicts, extras: list of names).
    """
    resolve_s = prof["preflight"]["resolve_seconds"]
    flow_s = prof["preflight"]["flow_seconds"]
    print(f"Resolving LSL streams ({resolve_s:.0f}s)...")
    found = resolve_streams(wait_time=resolve_s)
    by_name = {}
    for s in found:
        by_name.setdefault(s.name(), []).append(s)

    expected = prof.get("streams", [])
    matched_names = set()
    results = []

    # Collect sample counts for every matched stream in one shared window
    flow_inlets = []  # (result_index, inlet)
    for spec in expected:
        if "name" in spec:
            matches = by_name.get(spec["name"], [])
            label = spec["name"]
            lo = spec.get("min_count", 1)
            hi = spec.get("max_count", 1)
        else:
            prefix = spec["prefix"]
            matches = [s for n, ss in by_name.items() if n.startswith(prefix) for s in ss]
            label = prefix + "*"
            lo = spec.get("min_count", 1)
            hi = spec.get("max_count", 99)

        for s in matches:
            matched_names.add(s.name())

        r = {
            "label": label,
            "required": spec.get("required", True),
            "found": len(matches),
            "expected": f"{lo}" if lo == hi else f"{lo}-{hi}",
            "count_ok": lo <= len(matches) <= hi,
            "check_flow": spec.get("check_flow", False),
            "flow_hz": None,
            "flow_ok": None,
            "names": sorted({s.name() for s in matches}),
        }
        results.append(r)
        if r["check_flow"] and matches:
            for s in matches:
                # recover=False: these are throwaway probe inlets; without it,
                # closing them spams liblsl reconnection errors to stderr
                flow_inlets.append((len(results) - 1,
                                    StreamInlet(s, max_buflen=10, recover=False)))

    if flow_inlets:
        print(f"Checking flow ({flow_s:.0f}s)...")
        t_end = time.time() + flow_s
        counts = {i: 0 for i, _ in enumerate(flow_inlets)}
        while time.time() < t_end:
            for i, (_, inlet) in enumerate(flow_inlets):
                chunk, _ = inlet.pull_chunk(timeout=0.0)
                counts[i] += len(chunk)
            time.sleep(0.1)
        per_result = {}
        for i, (ridx, inlet) in enumerate(flow_inlets):
            per_result.setdefault(ridx, []).append(counts[i])
            inlet.close_stream()
        for ridx, cs in per_result.items():
            r = results[ridx]
            r["flow_hz"] = round(min(cs) / flow_s, 2)
            r["flow_ok"] = all(c > 0 for c in cs)

    extras = sorted(set(by_name) - matched_names)
    ok = True
    for r in results:
        this_ok = r["count_ok"] and (r["flow_ok"] is not False)
        if r["required"] and not this_ok:
            ok = False
    return ok, results, extras


def print_preflight(ok, results, extras):
    print("\n== PREFLIGHT ==")
    wid = max(len(r["label"]) for r in results) + 2
    for r in results:
        status = "PASS" if (r["count_ok"] and r["flow_ok"] is not False) else \
                 ("FAIL" if r["required"] else "warn")
        flow = ""
        if r["check_flow"]:
            flow = f"  flow={'ok' if r['flow_ok'] else 'NONE'}" \
                   + (f" ({r['flow_hz']}/s)" if r["flow_hz"] else "")
        count = f"found {r['found']} (expect {r['expected']})"
        print(f"  [{status}] {r['label']:<{wid}} {count}{flow}")
        if r["found"] and len(r["names"]) > 1:
            for n in r["names"]:
                print(f"           - {n}")
    if extras:
        print(f"  [info] unexpected streams present: {', '.join(extras)}")
    print(f"== {'ALL CLEAR' if ok else 'NOT READY'} ==\n")


# ---------------------------------------------------------------------------
# LabRecorder remote control
# ---------------------------------------------------------------------------

class LabRecorderRC:
    """Client for LabRecorder's remote-control socket (default port 22345).

    Protocol: newline-terminated text commands - 'update', 'select all',
    'filename {template:...}', 'start', 'stop'. Verify command syntax
    against the installed LabRecorder version (tested against 1.18.x).
    """

    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=5)

    def send(self, cmd):
        self.sock.sendall((cmd + "\n").encode())
        time.sleep(0.3)  # LabRecorder processes commands asynchronously

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Session run
# ---------------------------------------------------------------------------

def run_session(prof, unit, run_no, force, profile_path):
    study = prof["session"]["study"]
    session_id = dt.datetime.now().strftime("%Y%m%d-%H%M")
    run_part = f"_R{run_no:02d}" if run_no else ""
    base = Path(os.path.expanduser(prof["session"]["out_dir"])) / study / unit / session_id
    base.mkdir(parents=True, exist_ok=True)
    stem = f"{study}_{unit}_{session_id}{run_part}"
    xdf_path = base / f"{stem}_lsl.xdf"
    manifest_path = base / f"{stem}_manifest.json"

    manifest = {
        "study": study, "unit": unit, "session": session_id,
        "run": run_no, "operator": getpass.getuser(),
        "profile": str(profile_path),
        "started_utc": dt.datetime.utcnow().isoformat() + "Z",
        "xdf": str(xdf_path), "events": [], "preflight": None,
        "verification": None, "notes": [],
    }

    ok, results, extras = preflight(prof)
    print_preflight(ok, results, extras)
    manifest["preflight"] = {"ok": ok, "streams": results, "extras": extras}
    if not ok and not force:
        print("Preflight failed; fix the streams above or rerun with --force.")
        _write_manifest(manifest_path, manifest, aborted=True)
        return 1

    # Own marker outlet - operator annotations land in the recording
    info = StreamInfo("simcenter.orchestrator", "Markers", 1, 0, "string",
                      f"orchestrator-{socket.gethostname()}")
    marker_outlet = StreamOutlet(info)
    time.sleep(1.0)  # let LabRecorder discover it

    lr_cfg = prof["labrecorder"]
    print(f"Connecting to LabRecorder at {lr_cfg['host']}:{lr_cfg['port']}...")
    try:
        rc = LabRecorderRC(lr_cfg["host"], lr_cfg["port"])
    except OSError as e:
        print(f"Cannot reach LabRecorder's remote-control socket: {e}")
        print("Is LabRecorder running with RCS enabled on that port?")
        _write_manifest(manifest_path, manifest, aborted=True)
        return 1

    rc.send("update")
    time.sleep(1.0)
    rc.send("select all")
    rc.send("filename {template:%s}" % str(xdf_path))
    rc.send("start")
    t_start = local_clock()
    marker_outlet.push_sample(["session_start"])
    manifest["events"].append({"lsl_time": t_start, "label": "session_start"})
    print(f"\nRECORDING -> {xdf_path}")
    print("Type a label + Enter to drop a marker (e.g. 'clap', 'scenario start').")
    print("Type 'stop' to end the session.\n")

    try:
        while True:
            try:
                line = input("mark> ").strip()
            except EOFError:
                line = "stop"
            if not line:
                continue
            if line.lower() == "stop":
                break
            ts = local_clock()
            marker_outlet.push_sample([line], ts)
            manifest["events"].append({"lsl_time": ts, "label": line})
            print(f"  {line} @ {ts:.3f}")
    except KeyboardInterrupt:
        print("\n(Ctrl+C - stopping session)")

    ts = local_clock()
    marker_outlet.push_sample(["session_end"], ts)
    manifest["events"].append({"lsl_time": ts, "label": "session_end"})
    time.sleep(0.5)
    rc.send("stop")
    rc.close()
    print("Waiting for LabRecorder to finalize the file...")
    time.sleep(2.0)

    if xdf_path.exists():
        try:
            analysis = check_xdf.analyze(xdf_path)
            print()
            print(check_xdf.format_report(analysis))
            manifest["verification"] = _summarize(analysis)
        except Exception as e:
            manifest["notes"].append(f"verification failed: {e}")
            print(f"Verification failed: {e}")
    else:
        manifest["notes"].append("xdf missing after stop - was LabRecorder real "
                                 "(not the mock) and recording?")
        print(f"NOTE: no file at {xdf_path} - if you were testing against "
              "mock_labrecorder.py this is expected.")

    _write_manifest(manifest_path, manifest)
    return 0


def _summarize(analysis):
    return {
        "n_streams": analysis["n_streams"],
        "overlap_seconds": round(analysis["overlap"]["duration"], 1) if analysis["overlap"] else None,
        "warnings": analysis["warnings"],
        "continuous": [
            {"name": d["name"], "n": d["n_samples"],
             "effective_hz": round(d["effective_hz"], 2) if d["effective_hz"] else None,
             "flag": d.get("flag")}
            for d in analysis["continuous"]],
        "irregular": [
            {"name": d["name"], "n": d["n_samples"],
             "inside_window": d.get("inside_window")}
            for d in analysis["sparse"] + analysis["irregular"]],
    }


def _write_manifest(path, manifest, aborted=False):
    manifest["aborted"] = aborted
    manifest["finished_utc"] = dt.datetime.utcnow().isoformat() + "Z"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Manifest -> {path}")


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("preflight", help="check expected streams and exit")
    p1.add_argument("--profile", default=str(HERE / "profiles" / "default.toml"))

    p2 = sub.add_parser("run", help="preflight, record, annotate, verify, manifest")
    p2.add_argument("--profile", default=str(HERE / "profiles" / "default.toml"))
    p2.add_argument("--unit", required=True, help="team/subject pseudonym, e.g. T001")
    p2.add_argument("--run", type=int, default=0, help="run number within session")
    p2.add_argument("--force", action="store_true", help="record despite preflight failure")

    args = ap.parse_args()
    prof = load_profile(args.profile)

    if args.cmd == "preflight":
        ok, results, extras = preflight(prof)
        print_preflight(ok, results, extras)
        return 0 if ok else 1
    return run_session(prof, args.unit, args.run, args.force, args.profile)


if __name__ == "__main__":
    sys.exit(main())
