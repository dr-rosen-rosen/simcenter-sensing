# CPR joint-angle dataset — room setup, standards, and recording procedure

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-07-13

Protocol for recording a **CPR chest-compression dataset with 3D arm joint
angles** using the two-camera ZED rig. This specializes the general
single-subject arm-kinematics runbook
([session-protocol.md](session-protocol.md)) for CPR on a manikin; everything
not stated here follows that document.

**What the dataset measures per frame, per arm** (see
[data-spec.md](data-spec.md#arm-joint-angles)): elbow flexion, shoulder
elevation, plane of elevation, classic flexion/abduction, segment-length QA
signals, and a per-arm quality flag — plus full 3D joint positions, velocity,
and acceleration (wrist vertical excursion serves as a compression-depth
proxy).

**Why joint angles for CPR:** guideline technique is arms straight (elbows
locked), shoulders stacked vertically over the hands, pivoting from the hips.
Elbow flexion near 0° throughout the compression cycle is the signature of
correct technique; rising flexion indicates arm-pumping. Shoulder elevation /
plane track whether the shoulders stay over the sternum.

---

## Phase 1 — Room setup (CPR-specific)

The general placement rules in
[session-protocol.md Phase 1](session-protocol.md#phase-1--room-setup) apply.
CPR changes the geometry in three ways: the work volume is **low** (manikin
chest height), the rescuer **leans over** the work volume, and the two wrists
are **stacked** on the sternum (high self-occlusion risk).

1. **Manikin placement.** Manikin supine on the floor mat or a low platform,
   centered in the calibrated volume. Fix its position (tape outline) so it is
   identical across sessions — the calibration and the coverage analysis
   assume it.

2. **Pick and fix the rescuer side.** The rescuer works from **one documented
   side of the manikin for the whole dataset** (record which in the run
   sheet). Side switches mid-dataset change the occlusion pattern and
   complicate comparisons.

3. **Camera placement — across the manikin, frontal-oblique, high.** Place
   both cameras (`cam1` right, `cam2` left — see [hardware.md](hardware.md))
   on the **opposite side of the manikin from the rescuer**, flanking the
   rescuer's midline roughly symmetrically, angled inward and **steeply down**
   at the manikin's chest:
   - The rescuer's forward lean brings the head and shoulders toward the
     cameras; mount **above rescuer head height when kneeling-tall** and tilt
     down, so the shoulders don't occlude the wrists at full lean.
   - Keep both cameras' fields of view overlapping over the volume from the
     manikin's chest up to the rescuer's head — Fusion needs the overlap, and
     every angle joint (shoulders, elbows, wrists) must be inside it.
   - Keep the rescuer within the ZED depth sweet spot (typically a few
     meters; verify in the pilot).
   <!-- TODO(unassigned): Replace with pilot-verified mount heights, tilt angles, baseline separation, and camera-to-manikin distance; add a room diagram to assets/. -->

4. **Lighting.** Even, diffuse light on the rescuer and manikin chest; no
   backlight behind the rescuer; avoid strong overhead spot that shadows the
   chest when the rescuer leans in.

5. **Lock geometry, then calibrate.** Run **ZED360** after final mounting
   (procedure in [pre-session.md](pre-session.md#zed360-fusion-calibration)).
   During calibration, have the walking subject pass through the low work
   volume (crouch near the manikin) so the calibration is well-conditioned
   where the data actually happens.
   > [!IMPORTANT]
   > Recalibrate if a camera is bumped/moved, and treat the manikin tape
   > outline as part of the geometry — if the manikin moves, re-verify
   > coverage before recording.

---

## Phase 2 — Dataset standards

These make sessions comparable across days and trainees. Fixed for the whole
dataset; deviations go in the run sheet.

**Recording standards**
- Recorder: [`multiCameraRecord.py`](code/multiCameraRecord.py) — 30 fps,
  H.265 SVO2, one file per camera (`cam1_*/cam2_*` via the deployed
  `camera_roles.json`).
- Body model: `BODY_34` (default in `replay_fusion_enhanced.py`); do not mix
  body formats within a dataset.
- One continuous recording per session; bouts are segmented afterward by the
  run-sheet times and sync markers (do not stop/restart the recorder between
  bouts).

**Reference poses (recorded every session, in this order)**
1. **Standing calibration frame** — rescuer stands, arms hanging straight at
   the sides, ~5 s. Expect elbow flexion ≈ 0° and shoulder elevation ≈ 0°.
2. **Compression-start static hold** — hands stacked on the manikin's
   sternum, elbows locked, shoulders over hands, ~5 s, no compressions.
   Expect elbow flexion near 0°; this is the task-specific zero reference
   and the occlusion worst case — if quality flags fail here, fix the setup
   before recording bouts.

**Trial structure**
- Compressions-only (no ventilations) unless the study says otherwise.
- **Bouts of 2 minutes** at guideline rate (100–120 min⁻¹; metronome
  optional but if used, note the setting), separated by ≥ 1 minute rest.
  <!-- TODO(unassigned): Fix bout count per session and metronome policy once the study design is set. -->
- Mark each bout start/end verbally on the run sheet against the canonical
  clock; a hand-clap sync marker opens and closes the session
  ([../../docs/time-sync.md](../../docs/time-sync.md)).

**Naming and storage**
- Session IDs and filenames per
  [../../docs/identifiers.md](../../docs/identifiers.md); raw SVOs and derived
  CSVs stored per [../../docs/storage.md](../../docs/storage.md). No subject
  data in the repo.

**Session acceptance (QA gates)**
- Static holds read as expected: elbow flexion within tolerance of 0°
  (<!-- TODO(unassigned): set tolerance from pilot, e.g. ±10° -->).
- Per-arm `quality == "ok"` on ≥ <!-- TODO: e.g. 90% --> of compression-bout
  frames.
- `upperarm_len_m` / `forearm_len_m` stable across the session (no wild
  swings).
- Wrist vertical excursion shows a clear periodic signal at the metronome
  rate during bouts.
Sessions failing a gate are flagged, not silently included.

---

## Phase 3 — Recording procedure (per session)

1. **Pre-session** — run the condensed checklist in
   [session-protocol.md Phase 2](session-protocol.md#phase-2--pre-session-checklist-condensed):
   both cameras in `ZED_Explorer`, `camera_roles.json` deployed, calibration
   current, clock synced, Session ID created, disk capacity confirmed, test
   recording verified.
2. Position the manikin on its tape outline; rescuer briefed on the bout
   structure and reference poses.
3. Start the recorder (`python multiCameraRecord.py`); confirm **two**
   `recording to ...` lines (`cam1`, `cam2`).
4. **Opening sync marker** (hand clap visible to both cameras); note canonical
   time.
5. **Standing calibration frame** (~5 s).
6. **Compression-start static hold** (~5 s).
7. **Bout 1** — 2 min compressions; note start/end times. Rest ≥ 1 min.
   Repeat for the planned number of bouts.
8. **Closing sync marker**, then `Ctrl+C`. Confirm one `.svo2` per camera in
   `~/zed_rec/`, note sizes, and move to canonical storage paths.
9. Complete the run sheet (fields below).

**Processing** — as in
[session-protocol.md Phase 4](session-protocol.md#phase-4--processing-build-the-hybridized-3d--angles):
`replay_fusion_enhanced.py` with `ARM_ANGLES_ENABLED = True` produces
`fused_bodies.csv`; segment it into bouts using the run-sheet times relative
to the sync markers; then apply the Phase 2 QA gates. Temporal smoothing for
angle traces: `arm_joint_angles.py --smooth-window 5` as a starting point
(compressions at 2 Hz sampled at 30 fps tolerate a 5-frame window without
flattening peaks).

**Processing more than one session at a time** — once several sessions have
accumulated in the recordings directory, use
[`batch_process_sessions.py`](code/README.md) instead of running
`replay_fusion_enhanced.py` by hand per session:
```bash
python batch_process_sessions.py \
    --recordings-dir ~/zed_rec \
    --fusion-conf ~/zed_rec/fusion_calibration.json \
    --out-dir ~/cpr_dataset
```
It finds every `cam1`/`cam2` pair, writes each session's `fused_bodies.csv`
to its own subfolder under `--out-dir`, and skips sessions it's already
processed (`--force` to reprocess). Still apply the Phase 2 QA gates to each
session's output before folding it into the dataset.

---

## Run-sheet fields (this protocol)

Everything in [session-protocol.md](session-protocol.md#run-sheet-fields-for-this-protocol),
plus: rescuer side of manikin; manikin model + surface (floor / platform);
metronome on/off + rate; per-bout start/end times; static-hold time windows;
any technique deviations observed (bent elbows, side switch, interruptions).

## Related

- Field checklist for actually running a session: [pilot-session-checklist.md](pilot-session-checklist.md)
- General arm-kinematics runbook: [session-protocol.md](session-protocol.md)
- Angle definitions and schema: [data-spec.md](data-spec.md#arm-joint-angles)
- Angle math: [code/arm_joint_angles.py](code/arm_joint_angles.py) (`--selftest`)
- PI-facing summary: [pi-summary.md](pi-summary.md)
