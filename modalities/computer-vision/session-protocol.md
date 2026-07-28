# CV session protocol — single-subject procedural skills (arm kinematics)

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-07-13

End-to-end runbook for capturing **one trainee performing a procedural skill**
with the multi-camera ZED setup, and turning that capture into **3D arm
kinematics and joint angles**. This document stitches the per-phase SOPs
([hardware](hardware.md), [pre-session](pre-session.md),
[during-session](during-session.md), [processing](processing.md),
[data-spec](data-spec.md)) into a single flow for this specific use case.

**Why this setup:** the measurement is *markerless and unobtrusive* — no
goniometers, no reflective markers, no wearables on the trainee. Two cameras are
fused into a single 3D skeleton so that when one hand is occluded (by the body,
the table, or an instrument) the other camera still sees it.

---

## At a glance

```
   ROOM SETUP              RECORDING                PROCESSING              DATA
   ───────────             ─────────                ──────────             ────
   2 ZED cams,      →      multiCameraRecord.py →   replay_fusion_    →    fused_bodies.csv
   frontal-oblique         one .svo2 / camera       enhanced.py            (3D joints, velocity,
   ZED360 calibration      + sync markers           (fusion → 3D →         acceleration, ARM ANGLES)
                                                     angles)               demo_camN.avi, head_crops/
```

---

## Phase 1 — Room setup

Goal: both forearms and hands stay visible throughout the task, and the two
cameras share enough overlap for Fusion to reconstruct one clean 3D skeleton.

1. **Define the work volume.** The box in space where the trainee's hands
   operate (bench top, manikin, task trainer). Everything below is aimed at
   keeping that volume well-covered by *both* cameras.

2. **Place two ZED cameras frontal-oblique.** Mount them flanking the front of
   the subject, roughly symmetric about the subject's midline, angled inward and
   downward at the work volume.
   - Aim for wide baseline separation while keeping large **field-of-view
     overlap** over the work volume — Fusion needs overlap to fuse.
   - Elevate above the subject's hands and tilt down so the torso/table doesn't
     occlude the hands. Frontal-oblique beats a pure side view for keeping both
     shoulders, elbows, and wrists in view.
   - Keep the subject within the ZED depth sweet spot (see
     [hardware.md](hardware.md); typically a few meters — tune in the pilot).
   <!-- TODO(unassigned): Replace with pilot-verified angles/distances/heights and add a room diagram to assets/. -->

3. **Lighting.** Even, diffuse light on the subject; avoid backlight and bright
   windows behind the subject. ZED depth quality depends on scene texture and
   lighting (see [hardware.md](hardware.md)).

4. **Lock the geometry, then calibrate.** Once cameras are in their final
   mounted positions, run **ZED360** to produce `fusion_calibration.json`
   (full procedure in [pre-session.md](pre-session.md#zed360-fusion-calibration)).
   > [!IMPORTANT]
   > Calibration is geometry-sensitive. If a camera is bumped or moved after
   > calibration, **recalibrate** — otherwise the fused 3D skeleton (and every
   > angle derived from it) is wrong.

---

## Phase 2 — Pre-session checklist (condensed)

Full list in [pre-session.md](pre-session.md#per-session-checklist). The
essentials for this protocol:

- [ ] `conda activate ZED_env`; `ZED_Explorer` shows **both** cameras; record
      both serials in the run sheet.
- [ ] `camera_roles.json` (serial → `cam1`/`cam2` map, kept in `STAGING/cv/`)
      deployed next to `multiCameraRecord.py` so files come out as
      `cam1_*` / `cam2_*` — see [code/README.md](code/README.md).
- [ ] `fusion_calibration.json` current (recalibrated if anything moved).
- [ ] Lenses clean; lighting matches documented level; disk has capacity.
- [ ] ZedBox clock synced ([../../docs/time-sync.md](../../docs/time-sync.md));
      Session ID created ([../../docs/identifiers.md](../../docs/identifiers.md)).
- [ ] **Calibration-frame capture planned:** a few seconds of the trainee
      standing with arms hanging straight at their sides (used later as a 0°
      reference to sanity-check the angles — see Phase 5).
- [ ] Test recording opened and verified before the subject arrives.

---

## Phase 3 — Recording

Driven by [`multiCameraRecord.py`](code/multiCameraRecord.py). Full SOP in
[during-session.md](during-session.md).

1. Note the canonical-clock timestamp in the run sheet.
2. Capture the **opening sync marker** visible to both cameras (hand clap /
   flash — [../../docs/time-sync.md](../../docs/time-sync.md)).
3. Have the trainee do the **calibration-frame** pose (arms straight down, a few
   seconds) at the start.
4. Start the recorder:
   ```bash
   conda activate ZED_env
   cd modalities/computer-vision/code
   python multiCameraRecord.py     # Ctrl+C to stop
   ```
5. Confirm one `recording to ...` line **per camera**. If a camera is missing,
   stop and fix before proceeding.
6. Run the procedural task.
7. At the end: **closing sync marker**, then `Ctrl+C`. Confirm one `.svo2` per
   camera in `~/zed_rec/`; note sizes/durations; move to canonical paths per
   [../../docs/storage.md](../../docs/storage.md).

---

## Phase 4 — Processing (build the hybridized 3D + angles)

Driven by [`replay_fusion_enhanced.py`](code/replay_fusion_enhanced.py). Full
notes in [processing.md](processing.md).

1. Edit the `USER CONFIG` block:
   - `SVO_FILES` → the two recorded SVOs.
   - `FUSION_CONF` → the `fusion_calibration.json` from Phase 1.
   - `OUT_CSV` → destination for `fused_bodies.csv`.
   - `BODY_FORMAT` → `BODY_34` (default) or `BODY_38` (extra extremity joints).
   - `ARM_ANGLES_ENABLED = True` (on by default) appends arm-angle columns.
2. Run it:
   ```bash
   python replay_fusion_enhanced.py
   ```
   This opens both SVOs, runs body tracking per camera, fuses them into a single
   3D skeleton in world coordinates, and writes `fused_bodies.csv` (3D joints +
   velocity + acceleration + head/gaze + **arm joint angles**), plus optional
   `demo_camN.avi` overlays and `head_crops/`.
3. **(Optional) angles from an existing CSV.** The angle math is also a
   standalone tool:
   ```bash
   python arm_joint_angles.py fused_bodies.csv fused_with_angles.csv --smooth-window 5
   python arm_joint_angles.py --selftest      # validates the angle math
   ```

---

## Phase 5 — What data you get (and how to check it)

Full schema in [data-spec.md](data-spec.md); PI-facing framing in
[pi-summary.md](pi-summary.md). For this single-subject arm-kinematics protocol,
the headline outputs are:

- **3D arm joint angles per frame** (both arms): elbow flexion, shoulder
  elevation, and plane-of-elevation, plus classic flexion/abduction. These feed
  range-of-motion, ergonomic-exposure, and movement-smoothness analyses.
- **3D joint kinematics**: position, velocity, acceleration for every joint.
- **Annotated video + head crops** for qualitative review.

**Sanity checks before trusting a session:**

1. **Check the person count first.** The run prints a `[PEOPLE]` summary. It must
   match how many people were actually in the room. If one subject comes out as
   two or more `person_id`s, the world coordinate convention does not match the
   ZED360 calibration, and **every angle from that run is invalid** — the same
   body has been reconstructed into two different frames. Fix it before looking
   at anything else:
   ```bash
   python diagnose_fusion_frame.py --svo cam1.svo2 --svo cam2.svo2 --fusion-conf fusion_calibration.json --fast
   ```
   then set the recommended `COORD_SYSTEM` in `replay_fusion_enhanced.py` and
   re-run. See changes.txt (2026-07-27) for the worked example.
2. In the **calibration-frame** window (arms straight down), `elbow_flexion_deg`
   should be near **0°** and `shoulder_elevation_deg` near **0°**. Large offsets
   flag a calibration or coordinate-frame problem.
3. The QA columns `upperarm_len_m` / `forearm_len_m` should be roughly constant
   across the session; wild variation flags bad tracking for those frames.
4. Filter to `L_quality == "ok"` / `R_quality == "ok"` for analysis; the other
   flag values tell you *why* a frame was dropped.

---

## Run-sheet fields for this protocol

Record per session: Session ID; both camera serials; calibration file path +
date; opening/closing sync-marker times; calibration-frame time window; task
name; start/stop times; SVO paths + sizes; operator; notes/anomalies.

## Related

- CPR specialization of this protocol: [cpr-joint-angles-protocol.md](cpr-joint-angles-protocol.md)
- Data schema: [data-spec.md](data-spec.md)
- PI-facing summary: [pi-summary.md](pi-summary.md)
- Code inventory: [code/README.md](code/README.md)
- Cross-modality time alignment: [../../docs/time-sync.md](../../docs/time-sync.md)
