# Computer vision code

Working Python source for the ZedBox-based CV pipeline. Run on the ZedBox
itself (or any host with the ZED SDK and `pyzed` installed). See
[../pre-session.md](../pre-session.md) for the conda environment setup.

| File                          | Stage         | Purpose                                                    |
|-------------------------------|---------------|------------------------------------------------------------|
| `multiCameraRecord.py`        | Recording     | Headless multi-camera SVO2 recording — one thread per ZED, H.265 compression, Ctrl-C to stop. |
| `replay_fusion_enhanced.py`   | Processing    | Offline fusion + analytics over recorded SVOs: body tracking, 3D fused skeletons, velocity/acceleration, head-frame computation, optional head crops, optional annotated demo videos. |
| `gaze_geometry.py`            | Processing    | Head-frame + forward-direction computation from BODY_34 / BODY_38 keypoints, with quality-flag fallbacks. Imported by `replay_fusion_enhanced.py`. |
| `projection_helpers.py`       | Processing    | SE3 inversion, world→image projection, fusion-calibration loader (`fusion_calibration.json`), intrinsics from `CameraInformation`. Imported by `replay_fusion_enhanced.py`. |
| `offload_session.sh`          | Post-session  | Push a session's SVO2 dir to the analysis laptop over SSH (scp + remote SHA-256 verification via PowerShell — stock Windows OpenSSH, no rsync), delete local copy only after verify. `--dry-run` / `--keep`; config via `ZED_OFFLOAD_HOST` etc. |

## How they fit together

```
multiCameraRecord.py        →  N × SVO2 files
                                   ↓
                          (ZED360 calibration)
                                   ↓
replay_fusion_enhanced.py   →  fused_bodies.csv  (3D kinematics)
   ├─ projection_helpers.py     +  demo_camN.avi   (2D overlays + gaze arrows)
   └─ gaze_geometry.py          +  head_crops/     (optional)
```

## Configuration

`replay_fusion_enhanced.py` has a `USER CONFIG` block near the top
(`SVO_FILES`, `FUSION_CONF`, `OUT_CSV`, depth/body model selection, etc.).
Edit these for each session.

## TODOs

<!-- TODO(unassigned): Pull config into a YAML/JSON file or CLI args so the script isn't edited per-run -->
<!-- TODO(unassigned): Verify BODY_34 / BODY_38 keypoint indices in gaze_geometry.py against the ZED SDK version actually in use; document in a header comment -->
<!-- TODO(unassigned): Replace the GazeEstimator placeholder with the chosen gaze model (Gaze360 or similar); document in processing.md -->
