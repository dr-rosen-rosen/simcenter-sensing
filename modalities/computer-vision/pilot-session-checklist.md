# CPR pilot-session field checklist

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-07-21

A literal, in-order checklist for today's first room setup and recording,
distilled from [cpr-joint-angles-protocol.md](cpr-joint-angles-protocol.md).
Fill in every blank below as you go — those numbers close out the TODOs in
that document once you're done, so they don't stay generic guesses forever.

---

## A. Room & camera setup

- [ ] Manikin positioned; **tape its outline** on the floor/platform.
- [ ] Rescuer side chosen and fixed for the whole dataset: ______________
- [ ] Both cameras mounted **across from the rescuer**, frontal-oblique,
      angled down at the manikin's chest (see rationale in
      [cpr-joint-angles-protocol.md Phase 1](cpr-joint-angles-protocol.md#phase-1--room-setup-cpr-specific)).
- [ ] Measure and record:
  - Mount height (floor to camera): `cam1 (right? ___): _____` `cam2 (left? ___): _____`
  - Tilt angle (downward from horizontal): `cam1: _____°` `cam2: _____°`
  - Baseline separation (distance between the two cameras): `_____`
  - Camera-to-manikin distance: `_____`
- [ ] Lighting checked: even/diffuse on rescuer + chest, no backlight, no
      shadow-casting overhead spot when rescuer leans in.
- [ ] `ZED_Explorer` (from `/usr/local/zed/tools/`) shows **both** serials
      (`45817796` / `44429816`) before touching anything else.

## B. Calibration

- [ ] Geometry locked (nothing will move after this point).
- [ ] Run **ZED360**; walk/crouch the calibration subject through the low
      work volume near the manikin, not just standing upright.
- [ ] Calibration converged — record convergence time: `_____`
- [ ] `fusion_calibration.json` saved — path: `_____`
- [ ] Sanity check: standing + static-hold reference poses (below) read near
      0° elbow flexion once you process a quick test clip.

## C. Pre-recording checklist

- [ ] `conda activate ZED_env`
- [ ] `camera_roles.json` present next to `multiCameraRecord.py` on the
      ZedBox (confirms `cam1`=`7796`, `cam2`=`9816` labeling).
- [ ] Session ID created per [docs/identifiers.md](../../docs/identifiers.md): `_____`
- [ ] ZedBox clock synced per [docs/time-sync.md](../../docs/time-sync.md).
- [ ] Disk capacity checked against expected session length.
- [ ] Brief test recording (a few seconds, Ctrl+C, confirm both `.svo2`s
      open in `ZED_Explorer`) — **do this before the rescuer arrives.**

## D. Recording sequence (do not skip steps or reorder)

1. Rescuer briefed on bout structure and the two reference poses below.
2. Start: `python multiCameraRecord.py` — confirm **two**
   `recording to ...` lines (`cam1`, `cam2`). If only one appears, stop and
   fix before continuing.
3. **Opening sync marker** (hand clap, visible to both cameras) — note the
   canonical-clock time: `_____`
4. **Standing calibration frame** (~5 s, arms hanging straight down).
   Time window: `_____` to `_____`
5. **Compression-start static hold** (~5 s, hands stacked on sternum, elbows
   locked, no compressions). Time window: `_____` to `_____`
6. **Bout 1**: 2 min compressions, guideline rate 100–120/min.
   Metronome: on/off `_____`, rate if on: `_____`
   Start: `_____` End: `_____`
   Rest ≥ 1 min, then repeat for each planned bout (add rows as needed):
   - Bout 2 — Start: `_____` End: `_____`
   - Bout 3 — Start: `_____` End: `_____`
7. **Closing sync marker**, then `Ctrl+C`.
8. Confirm one `.svo2` per camera in `~/zed_rec/`; note file sizes:
   `cam1: _____` `cam2: _____`
9. Move files to canonical storage per [docs/storage.md](../../docs/storage.md).

## E. Immediately after — process the test clip

Run `replay_fusion_enhanced.py` (`ARM_ANGLES_ENABLED = True`) on this
session before the rescuer leaves, if at all possible, so you can catch a
bad calibration or occlusion problem while you can still fix it and re-shoot:

- [ ] Standing calibration frame reads elbow flexion near 0°: measured value `_____`
- [ ] Static hold reads elbow flexion near 0°: measured value `_____`
      → **this is the tolerance to record back into the main protocol
      as the QA gate.**
- [ ] `L_quality`/`R_quality == "ok"` fraction during a bout: `_____%`
      → **this is the QA-gate threshold to record back.**
- [ ] `upperarm_len_m` / `forearm_len_m` look stable across the session
      (no wild swings).
- [ ] Wrist vertical excursion shows a clear periodic signal at the
      compression rate.

## F. Numbers to fold back into `cpr-joint-angles-protocol.md`

Once this pilot is done, report back:

- Mount heights / tilt angles / baseline separation / camera-to-manikin
  distance (Section A)
- Elbow-flexion tolerance observed at the static hold (Section E)
- Quality-flag pass rate observed during a bout (Section E)
- Final bout count / metronome policy, once decided

I'll fold these into the doc's TODOs and mark those sections
pilot-verified instead of drafted guesses.

## Related

- Full protocol (room setup rationale, dataset standards, QA gates): [cpr-joint-angles-protocol.md](cpr-joint-angles-protocol.md)
- General arm-kinematics runbook: [session-protocol.md](session-protocol.md)
