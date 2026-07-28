# Computer vision code

Working Python source for the ZedBox-based CV pipeline. Run on the ZedBox
itself (or any host with the ZED SDK and `pyzed` installed). See
[../pre-session.md](../pre-session.md) for the conda environment setup.

| File                          | Stage         | Purpose                                                    |
|-------------------------------|---------------|------------------------------------------------------------|
| `multiCameraRecord.py`        | Recording     | Headless multi-camera SVO2 recording — one thread per ZED, H.265 compression, Ctrl-C to stop. |
| `replay_fusion_enhanced.py`   | Processing    | Offline fusion + analytics over recorded SVOs: body tracking, 3D fused skeletons, velocity/acceleration, head-frame computation, arm joint angles, optional head crops, optional annotated demo videos. Exposes `process_session(svo_files, fusion_conf, out_csv, ...)` for reuse. |
| `batch_process_sessions.py`   | Processing    | Runs `process_session()` over every `cam1`/`cam2` SVO2 pair found in a recordings directory — builds a dataset without hand-editing `replay_fusion_enhanced.py` per session. Skips sessions already processed unless `--force`. |
| `arm_joint_angles.py`         | Processing    | Elbow + shoulder joint angles from fused 3D keypoints (BODY_34/38), using a subject-anchored anatomical frame. Imported by `replay_fusion_enhanced.py`; also runs standalone on a `fused_bodies.csv` and has a `--selftest`. |
| `diagnose_fusion_frame.py`    | Diagnostic    | Finds the world `COORDINATE_SYSTEM` that merges the cameras' views of one person into a single fused `person_id`. Run once per camera setup / recalibration, then set `COORD_SYSTEM` in `replay_fusion_enhanced.py`. |
| `gaze_geometry.py`            | Processing    | Head-frame + forward-direction computation from BODY_34 / BODY_38 keypoints, with quality-flag fallbacks. Imported by `replay_fusion_enhanced.py`. |
| `projection_helpers.py`       | Processing    | SE3 inversion, world→image projection, fusion-calibration loader (`fusion_calibration.json`), intrinsics from `CameraInformation`. Imported by `replay_fusion_enhanced.py`. |

## How they fit together

```
multiCameraRecord.py        →  N × SVO2 files (cam1_*, cam2_*, one pair per session)
                                   ↓
                          (ZED360 calibration)
                                   ↓
batch_process_sessions.py   →  loops over every cam1/cam2 pair, calling:
   replay_fusion_enhanced.py   →  fused_bodies.csv  (3D kinematics + arm angles)
      ├─ projection_helpers.py     +  demo_camN.avi   (2D overlays + gaze arrows)
      ├─ gaze_geometry.py          +  head_crops/     (optional)
      └─ arm_joint_angles.py
```

## Configuration

`replay_fusion_enhanced.py` has a `USER CONFIG` block near the top for
settings that are fixed **dataset-wide** (depth/body model, angle/video
toggles, etc. — see [cpr-joint-angles-protocol.md](../cpr-joint-angles-protocol.md#phase-2--dataset-standards)
on why these shouldn't vary within one dataset). Edit these once, before
starting a dataset, not per session.

Per-session paths (`SVO_FILES`, `FUSION_CONF`, `OUT_CSV`, `HEAD_CROP_DIR`,
`VIDEO_DIR`) no longer need hand-editing to process more than one session:

- **One-off / ad hoc:** `python replay_fusion_enhanced.py` still uses the
  `USER CONFIG` paths directly.
- **A dataset (recommended):**
  ```bash
  python batch_process_sessions.py \
      --recordings-dir ~/zed_rec \
      --fusion-conf ~/zed_rec/fusion_calibration.json \
      --out-dir ~/cpr_dataset
  ```
  Finds every `cam1_<stamp>.svo2` / `cam2_<stamp>.svo2` pair, and writes each
  session's `fused_bodies.csv` (+ `head_crops/`, `demos/` if enabled) to
  `~/cpr_dataset/<stamp>/`. Re-running skips sessions already processed
  unless you pass `--force`.

`multiCameraRecord.py` maps camera serials to stable labels (`cam1`/`cam2`)
via a `camera_roles.json` deployed next to it, e.g.
`{"12345678": "cam1", "87654321": "cam2"}`. The real file contains full
serials, so it is **not committed** — it lives in `STAGING/cv/` and gets
copied to the ZedBox alongside this script (see
[docs/identifiers.md](../../../docs/identifiers.md), rule 4). Without it,
unmapped cameras still record safely as `cam-SN<serial>_*.svo2`.

## TODOs

<!-- TODO(unassigned): Pull the dataset-wide USER CONFIG constants (depth/body model, angle/video toggles) into a YAML/JSON file too, so a new dataset doesn't require editing the script at all -->
<!-- TODO(unassigned): Verify BODY_34 / BODY_38 keypoint indices in gaze_geometry.py against the ZED SDK version actually in use; document in a header comment -->
<!-- TODO(unassigned): Replace the GazeEstimator placeholder with the chosen gaze model (Gaze360 or similar); document in processing.md -->
