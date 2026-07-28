# Computer vision

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## Scope

Camera-based extraction of pose (3D body keypoints), head frame, and
heuristic gaze direction during simulation sessions, from a multi-camera ZED
setup driven by the Stereolabs SDK + Fusion module on a ZedBox.

## Current platform

**ZedBox** + multiple ZED cameras, recording to SVO2 and processed offline via
`code/replay_fusion_enhanced.py`. The earlier Intel RealSense workflow is
preserved under [`_archive/intel-cameras/`](_archive/intel-cameras/README.md)
for reference only (status: archived).

## Vendor references

- ZED SDK Python virtual env setup: <https://www.stereolabs.com/docs/development/python/virtual_env>
- Multi-camera body tracking example: <https://github.com/stereolabs/zed-sdk/blob/master/body%20tracking/multi-camera/python/fused_cameras.py>
- Multi-camera recording example: <https://github.com/stereolabs/zed-sdk/tree/master/recording/recording/multi%20camera/python>

## Section status

| Section          | File                                       | Status      |
|------------------|--------------------------------------------|-------------|
| Hardware         | [hardware.md](hardware.md)                 | drafted     |
| Pre-session      | [pre-session.md](pre-session.md)           | drafted     |
| During-session   | [during-session.md](during-session.md)     | drafted     |
| Troubleshooting  | [troubleshooting.md](troubleshooting.md)   | stub        |
| Processing       | [processing.md](processing.md)             | drafted     |
| Data spec        | [data-spec.md](data-spec.md)               | drafted     |
| Code             | [code/README.md](code/README.md)           | drafted     |
| Session protocol (single-subject arm kinematics) | [session-protocol.md](session-protocol.md) | drafted |
| CPR joint-angle dataset protocol | [cpr-joint-angles-protocol.md](cpr-joint-angles-protocol.md) | drafted |
| CPR pilot-session field checklist | [pilot-session-checklist.md](pilot-session-checklist.md) | drafted |
| PI summary       | [pi-summary.md](pi-summary.md)             | drafted     |

## TODOs for collaborators

- [ ] Fill the ZedBox hardware table in [hardware.md](hardware.md) (model, SDK version, camera count)
- [ ] Quantify per-hour disk use for the chosen recording profile ([pre-session.md](pre-session.md))
- [ ] Populate [troubleshooting.md](troubleshooting.md) from pilot-session notes
- [ ] Verify BODY_34 / BODY_38 keypoint indices in `code/gaze_geometry.py` against deployed SDK
- [ ] Decide and document a gaze model to plug into `GazeEstimator.predict()`
- [ ] Lift `USER CONFIG` block in `replay_fusion_enhanced.py` to a YAML or CLI args
- [ ] Add a room/coverage diagram under `assets/`
- [ ] Write a small renamer helper to convert `~/zed_rec/<serial>.svo2` to the canonical session filename
