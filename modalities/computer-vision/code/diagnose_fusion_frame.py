#!/usr/bin/env python3
"""
diagnose_fusion_frame.py
========================

Find the world COORDINATE_SYSTEM that makes Fusion merge your cameras'
views of one person into a SINGLE fused person_id.

Why this exists
---------------
The ZED360 `fusion_calibration.json` expresses each camera's pose in some
world convention. The clients and Fusion must be initialized in that SAME
convention. If they aren't, each camera's skeleton is placed into a different
part of world space and Fusion emits ONE PERSON AS SEVERAL person_ids --
silently. Every CSV row still looks confident and well-formed, so the error is
easy to miss and it corrupts every angle derived from it.

This tool re-runs a short fusion pass for each candidate convention and reports
how many people came out. Run it once per camera setup / recalibration, then
put the winner in `COORD_SYSTEM` at the top of replay_fusion_enhanced.py.

Usage
-----
    python diagnose_fusion_frame.py \
        --svo cam1.svo2 --svo cam2.svo2 \
        --fusion-conf fusion_calibration.json \
        [--max-frames 120] [--fast]

Interpreting the output
-----------------------
- `persons` is the headline: you want it to equal the number of people who
  were really in the room (usually 1 for a single-subject protocol).
- `resid_cm` / `rot_deg` compare two tracks as rigid bodies. A SMALL residual
  with a LARGE rotation means the tracks are the same body reconstructed into
  two different frames -- i.e. a frame mismatch, not two people.
- Prefer a RIGHT-HANDED winner. A left-handed world silently mirrors the
  forward/back and left/right axes of the cross-product anatomical frame in
  arm_joint_angles.py, flipping plane-of-elevation and abduction with no error
  raised. The tool flags handedness for you.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pyzed.sl as sl

import replay_fusion_enhanced as rfe
from projection_helpers import load_extrinsics_from_fusion_conf

# Candidate conventions, with handedness. IMAGE is X right / Y down / Z forward
# (the OpenCV convention) and is right-handed.
CANDIDATES = [
    ("IMAGE",                   sl.COORDINATE_SYSTEM.IMAGE,                   "right"),
    ("RIGHT_HANDED_Z_UP",       sl.COORDINATE_SYSTEM.RIGHT_HANDED_Z_UP,       "right"),
    ("RIGHT_HANDED_Y_UP",       sl.COORDINATE_SYSTEM.RIGHT_HANDED_Y_UP,       "right"),
    ("RIGHT_HANDED_Z_UP_X_FWD", sl.COORDINATE_SYSTEM.RIGHT_HANDED_Z_UP_X_FWD, "right"),
    ("LEFT_HANDED_Y_UP",        sl.COORDINATE_SYSTEM.LEFT_HANDED_Y_UP,        "left"),
    ("LEFT_HANDED_Z_UP",        sl.COORDINATE_SYSTEM.LEFT_HANDED_Z_UP,        "left"),
]


def _rigid_align(A: np.ndarray, B: np.ndarray):
    """Rigid Procrustes A -> B (rotation + translation, no scale).

    Returns (mean_residual_metres, rotation_degrees). Rows are corresponding
    3D points; rows that are non-finite in either set are dropped.
    """
    good = np.isfinite(A).all(axis=1) & np.isfinite(B).all(axis=1)
    A, B = A[good], B[good]
    if len(A) < 3:
        return float("nan"), float("nan")
    ca, cb = A.mean(0), B.mean(0)
    A0, B0 = A - ca, B - cb
    U, _, Vt = np.linalg.svd(A0.T @ B0)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    resid = float(np.sqrt(((B0 - A0 @ R.T) ** 2).sum(1)).mean())
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    return resid, ang


def run_candidate(svo_files, fusion_conf, coord_system, max_frames, depth_mode):
    """Run a short fusion pass under one convention.

    Returns dict(persons, counts, frames, resid_cm, rot_deg, sep_m) or
    {"error": "..."} if the pass could not be set up.
    """
    rfe.COORD_SYSTEM = coord_system  # read by open_client_from_svo() and init_fusion()

    clients = []
    try:
        for p in svo_files:
            cam = rfe.open_client_from_svo(p, depth_mode)
            if cam is None:
                return {"error": f"could not open {os.path.basename(p)}"}
            if not rfe.enable_bt_and_publish(cam):
                return {"error": "body tracking / publish failed"}
            clients.append(cam)

        serials = [int(c.get_camera_information().serial_number) for c in clients]
        Twc_map = load_extrinsics_from_fusion_conf(fusion_conf)

        fusion = rfe.init_fusion()
        if fusion is None:
            return {"error": "fusion init failed"}
        if not rfe.add_inputs_to_fusion(fusion, serials, Twc_map):
            return {"error": "fusion subscribe failed"}
        if not rfe.enable_fusion_body_tracking(fusion):
            return {"error": "fusion enable_body_tracking failed"}

        rt = [sl.RuntimeParameters() for _ in clients]
        bt_rt = sl.BodyTrackingFusionRuntimeParameters()
        counts, kp_by_pid, head_by_pid = {}, {}, {}
        frames = 0
        active = True

        while active and frames < max_frames:
            active = False
            for i, cam in enumerate(clients):
                if cam.grab(rt[i]) == sl.ERROR_CODE.SUCCESS:
                    active = True
            if fusion.process() == sl.FUSION_ERROR_CODE.SUCCESS:
                fused = sl.Bodies()
                fusion.retrieve_bodies(fused, bt_rt)
                for b in fused.body_list:
                    pid = int(b.id)
                    counts[pid] = counts.get(pid, 0) + 1
                    kp = np.asarray(b.keypoint, dtype=float)
                    kp_by_pid.setdefault(pid, kp)  # keep first good skeleton
                    if np.isfinite(kp).any():
                        head_by_pid.setdefault(pid, np.nanmean(kp, axis=0))
            frames += 1

        out = {"persons": len(counts), "counts": counts, "frames": frames}
        # If it split, quantify whether the two biggest tracks are one body.
        if len(counts) >= 2:
            top = sorted(counts, key=counts.get, reverse=True)[:2]
            A, B = kp_by_pid.get(top[0]), kp_by_pid.get(top[1])
            if A is not None and B is not None and A.shape == B.shape:
                resid, ang = _rigid_align(A, B)
                out["resid_cm"] = resid * 100.0
                out["rot_deg"] = ang
            ha, hb = head_by_pid.get(top[0]), head_by_pid.get(top[1])
            if ha is not None and hb is not None:
                out["sep_m"] = float(np.linalg.norm(ha - hb))
        return out
    finally:
        for cam in clients:
            try:
                cam.stop_publishing(); cam.disable_body_tracking(); cam.close()
            except Exception:
                pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svo", action="append", required=True,
                    help="SVO2 file (repeat once per camera)")
    ap.add_argument("--fusion-conf", required=True, help="ZED360 fusion_calibration.json")
    ap.add_argument("--max-frames", type=int, default=120,
                    help="frames per candidate (default 120; higher = slower but surer)")
    ap.add_argument("--expect-people", type=int, default=1,
                    help="how many people were really in the room (default 1)")
    ap.add_argument("--fast", action="store_true",
                    help="use PERFORMANCE depth for speed instead of the pipeline default")
    args = ap.parse_args(argv)

    for p in args.svo + [args.fusion_conf]:
        if not os.path.exists(p):
            print(f"error: missing {p}", file=sys.stderr)
            return 2
    if len(args.svo) < 2:
        print("error: need at least two --svo files to diagnose fusion", file=sys.stderr)
        return 2

    depth = sl.DEPTH_MODE.PERFORMANCE if args.fast else rfe.DEPTH_MODE
    original = rfe.COORD_SYSTEM
    results = []
    try:
        for name, cs, hand in CANDIDATES:
            print(f"--- testing {name} ---", file=sys.stderr)
            try:
                res = run_candidate(args.svo, args.fusion_conf, cs, args.max_frames, depth)
            except Exception as e:  # a bad convention shouldn't kill the sweep
                res = {"error": str(e)[:60]}
            results.append((name, hand, res))
    finally:
        rfe.COORD_SYSTEM = original

    print(f"\n{'candidate':<26}{'hand':<7}{'persons':>8}{'resid_cm':>10}{'rot_deg':>9}{'sep_m':>8}")
    for name, hand, r in results:
        if "error" in r:
            print(f"{name:<26}{hand:<7}{'ERR':>8}   {r['error']}")
            continue
        f = lambda k, w, p=1: (f"{r[k]:>{w}.{p}f}" if k in r else " " * (w - 1) + "-")
        print(f"{name:<26}{hand:<7}{r['persons']:>8}{f('resid_cm',10)}{f('rot_deg',9)}{f('sep_m',8,2)}")

    ok = [(n, h, r) for n, h, r in results
          if "error" not in r and r["persons"] == args.expect_people]
    print()
    if not ok:
        print(f"No candidate produced exactly {args.expect_people} person(s).")
        print("Check that the calibration really belongs to these recordings, and")
        print("that both cameras actually saw the subject.")
        return 1

    right = [x for x in ok if x[1] == "right"]
    pick = right[0] if right else ok[0]
    print(f"Merged to {args.expect_people} person: " + ", ".join(f"{n} ({h}-handed)" for n, h, _ in ok))
    print(f"\nRecommended: COORD_SYSTEM = sl.COORDINATE_SYSTEM.{pick[0]}")
    if not right:
        print("WARNING: only LEFT-handed conventions merged correctly. A left-handed")
        print("world mirrors the forward/back and left/right axes of the anatomical")
        print("frame in arm_joint_angles.py -- shoulder plane-of-elevation and")
        print("abduction will come out flipped. Verify those signs before trusting them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
