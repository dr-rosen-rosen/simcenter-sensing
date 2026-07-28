# CV data spec

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## Raw

| File ext              | Source              | Notes |
|-----------------------|---------------------|-------|
| `.svo2`               | ZED SDK recording   | Stereo + depth, H.265-compressed by `multiCameraRecord.py`. Gitignored. One file per camera per session. |
| `fusion_calibration.json` | ZED360 export   | Multi-camera extrinsics. Per-camera-setup, regenerated on any geometric change. **Not subject data** but typically kept with the session for reproducibility. |

## Interim

Not currently a distinct stage — `replay_fusion_enhanced.py` consumes raw SVOs
and emits derived outputs directly.

<!-- TODO(unassigned): If a decoded/per-frame interim becomes useful (e.g., to share frames with another modality's pipeline), define its schema here. -->

## Derived

### `fused_bodies.csv`

Long-form-ish per-detected-body-per-frame. Column groups:

| Column                                       | Type   | Units                | Notes |
|----------------------------------------------|--------|----------------------|-------|
| `timestamp_ns`                               | int    | nanoseconds (SDK clock) | Fused-frame timestamp |
| `person_id`                                  | int    | —                    | Stable across frames (Fusion tracking) |
| `confidence`                                 | float  | 0-100                | SDK body confidence |
| `tracking_state`                             | int    | enum                 | SDK tracking-state enum |
| `k{i}_x`, `k{i}_y`, `k{i}_z`                 | float  | meters (world)       | Keypoint `i`. K=34 or 38 depending on `BODY_FORMAT`. |
| `k{i}_vx`, `k{i}_vy`, `k{i}_vz`              | float  | m/s                  | Finite-difference velocity, median-smoothed over short history. |
| `k{i}_ax`, `k{i}_ay`, `k{i}_az`              | float  | m/s²                 | Second-difference acceleration from consecutive velocities (zeros only on the first usable frame). |
| `head_x`, `head_y`, `head_z`                 | float  | meters (world)       | Head-frame origin, from `compute_head_frame_world()`. |
| `gaze_dx`, `gaze_dy`, `gaze_dz`              | float  | unit vector (world)  | Head-forward direction (heuristic; not eye-tracker gaze). |

#### Arm joint angles

Appended when `ARM_ANGLES_ENABLED` (default on), computed by
[`code/arm_joint_angles.py`](code/arm_joint_angles.py) from the fused 3D
keypoints. Columns are prefixed `L_` / `R_` for left / right arm.

| Column (per `L_`/`R_`)      | Type  | Units   | Notes |
|-----------------------------|-------|---------|-------|
| `elbow_flexion_deg`         | float | degrees | 0° straight, increasing as the elbow bends (= 180 − included angle). |
| `elbow_included_deg`        | float | degrees | Raw included angle between upper-arm and forearm segments (0–180). |
| `shoulder_elevation_deg`    | float | degrees | Humerus elevation from arm-down: 0° down, 90° horizontal, 180° up. |
| `shoulder_plane_deg`        | float | degrees | Plane of elevation: 0° forward flexion, +90° lateral abduction, ±180° extension (side-symmetric). |
| `shoulder_flexion_deg`      | float | degrees | Classic sagittal-plane angle (forward +, back −); degenerate under combined motions. |
| `shoulder_abduction_deg`    | float | degrees | Classic coronal-plane angle (out-to-side +, across-body −). |
| `upperarm_len_m`            | float | meters  | Shoulder→elbow length (QA signal). |
| `forearm_len_m`             | float | meters  | Elbow→wrist length (QA signal). |
| `quality`                   | str   | enum    | `ok` / `low_confidence` / `missing_joints` / `degenerate_trunk` / `degenerate_segment`. |

Angles use a subject-anchored anatomical frame (built from shoulders + hips), so
they are invariant to the world coordinate convention. Angle math is validated
by `arm_joint_angles.py --selftest`.

Missing-value convention: `NaN` for head/gaze when head-frame computation
fails (see `quality` flag values in `gaze_geometry.py`), and `NaN` for any arm
angle that could not be computed (with the reason in the per-arm `quality`
column).

Coordinate system: set by the `COORD_SYSTEM` constant in
`replay_fusion_enhanced.py` (currently `IMAGE`: X right, Y down, Z forward —
right-handed), applied identically to every camera client and to Fusion. This
**must** match the frame the ZED360 `fusion_calibration.json` extrinsics were
expressed in; a mismatch makes Fusion emit one person as several `person_id`s.
See changes.txt (2026-07-27, coordinate-system mismatch) for the sweep that
determined this. Arm angles are unaffected by the choice of right-handed world
frame — `arm_joint_angles.py` builds a subject-anchored anatomical frame.

### `demo_camN.avi`

Per-camera annotated MJPEG video with local 2D skeleton overlay and (when
projected) red gaze-arrow rays. **Re-identifiable** (contains video of
subjects) — treat as raw-subject-data tier per
[../../docs/data-governance.md](../../docs/data-governance.md).

### `head_crops/`

Heuristic upper-body bounding-box crops resized to 224x224, written when
`SAVE_HEAD_CROPS` is set (filenames `cam{n}_pid{id}_{frame:06d}.png`). Same
re-identification status as `demo_camN.avi`.

## Naming

Per [../../docs/identifiers.md](../../docs/identifiers.md):

```
<study>_<subject-or-team>_<session>[_<run>]_cv-<serial-tail>.svo2
```

For derived outputs, drop the per-camera tail since they're fused across cameras:

```
<study>_<subject-or-team>_<session>[_<run>]_cv-bodies.csv
```

<!-- TODO(unassigned): Wire the renaming into shared/identifiers/ helpers when those exist; the recorder currently writes `<serial>.svo2` only. -->
