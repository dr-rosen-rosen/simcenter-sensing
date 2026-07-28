#!/usr/bin/env python3
"""
Run replay_fusion_enhanced.py's fusion + arm-angle processing over every
cam1/cam2 SVO2 pair found in a recordings directory, instead of hand-editing
the USER CONFIG block once per session.

multiCameraRecord.py names files <label>_<session_stamp>.svo2, e.g.
cam1_2026-07-01_14-32-05.svo2 / cam2_2026-07-01_14-32-05.svo2 — files that
share a stamp are one session. Each session gets its own subfolder under
--out-dir (named by its stamp) containing fused_bodies.csv and, if enabled
in replay_fusion_enhanced.py, head_crops/ and demos/.

Usage:
    python batch_process_sessions.py \\
        --recordings-dir ~/zed_rec \\
        --fusion-conf ~/zed_rec/fusion_calibration.json \\
        --out-dir ~/cpr_dataset
"""
import argparse, os, re, sys, traceback
from collections import defaultdict

from replay_fusion_enhanced import process_session, SAVE_HEAD_CROPS, WRITE_DEMO_VIDEOS

FNAME_RE = re.compile(r"^(?P<label>[^_]+)_(?P<stamp>.+)\.svo2$")

def find_sessions(recordings_dir):
    sessions = defaultdict(dict)  # stamp -> {label: path}
    for fname in os.listdir(recordings_dir):
        m = FNAME_RE.match(fname)
        if not m:
            continue
        sessions[m.group("stamp")][m.group("label")] = os.path.join(recordings_dir, fname)
    return sessions

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recordings-dir", required=True, help="Directory of cam1_*/cam2_*.svo2 files, e.g. ~/zed_rec")
    ap.add_argument("--fusion-conf", required=True, help="fusion_calibration.json shared across sessions")
    ap.add_argument("--out-dir", required=True, help="Dataset root; one subfolder per session is created here")
    ap.add_argument("--force", action="store_true", help="Reprocess a session even if its fused_bodies.csv already exists")
    args = ap.parse_args()

    recordings_dir = os.path.expanduser(args.recordings_dir)
    out_root = os.path.expanduser(args.out_dir)
    fusion_conf = os.path.expanduser(args.fusion_conf)

    sessions = find_sessions(recordings_dir)
    if not sessions:
        print(f"No SVO2 files found in {recordings_dir}")
        return 1

    ok = skipped = failed = 0
    for stamp, files in sorted(sessions.items()):
        if len(files) < 2:
            print(f"[{stamp}] SKIP — only found {sorted(files)}, need both cameras present")
            skipped += 1
            continue

        session_out = os.path.join(out_root, stamp)
        out_csv = os.path.join(session_out, "fused_bodies.csv")
        if os.path.exists(out_csv) and not args.force:
            print(f"[{stamp}] SKIP — {out_csv} already exists (use --force to reprocess)")
            skipped += 1
            continue

        svo_files = [files[label] for label in sorted(files)]  # cam1 before cam2
        head_crop_dir = os.path.join(session_out, "head_crops") if SAVE_HEAD_CROPS else None
        video_dir = os.path.join(session_out, "demos") if WRITE_DEMO_VIDEOS else None

        print(f"[{stamp}] Processing {svo_files} -> {out_csv}")
        try:
            rc = process_session(svo_files, fusion_conf, out_csv,
                                  head_crop_dir=head_crop_dir, video_dir=video_dir)
        except Exception:
            traceback.print_exc()
            rc = 1

        if rc == 0:
            ok += 1
        else:
            print(f"[{stamp}] FAILED (exit {rc})")
            failed += 1

    print(f"\n{ok} processed, {skipped} skipped, {failed} failed — {len(sessions)} sessions found in {recordings_dir}")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
