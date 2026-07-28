# CV troubleshooting

> **Status:** stub
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

Symptoms collected from pilot sessions. Add entries as encountered; be
specific and reproducible.

<!-- TODO(unassigned): Populate from existing notes (Joplin, prior pilot debriefs) — see Phase 1 triage. -->

## Cameras missing from `ZED_Explorer` or `multiCameraRecord.py`

- **Cause:**
- **Fix:**
- **Prevention:** Power-cycle ZedBox + cameras before sessions; verify USB cabling.

## `[serial] open failed` in recorder console

- **Cause (all cameras fail at once, "Camera::open() has not been called" /
  "no Camera instance running"):** `cam.open()` was called concurrently from
  multiple threads — one per camera — at process start. The ZED SDK's
  GPU/CUDA context init on the first `open()` in a process isn't safe to
  race, so every concurrent `open()` can fail together. Fixed in
  `multiCameraRecord.py` by opening all cameras sequentially in the main
  thread first, then only parallelizing the grab loop afterward
  (`open_camera()` / `opened = [...]` in `main()`).
- **Cause (single camera):** another process (`ZED_Explorer`, `ZED360`, a
  previous unclosed run) already holds that camera open — only one client
  connection is allowed per camera — or a cabling/power issue on a shared USB
  hub, or the serial in `camera_roles.json` doesn't match a connected device.
- **Fix:** Kill stray `ZED_Explorer`/`ZED360`/Python processes (`ps aux | grep -i zed`)
  before recording; confirm both serials show in a standalone `ZED_Explorer`
  run with nothing else open; check cabling if only one camera is affected.

## Recording starts but `.svo2` file size stays at 0

- **Cause:**
- **Fix:**

## Disk fills mid-session

- **Cause:** SVO size at chosen resolution / FPS / depth exceeds estimate.
- **Fix:** Stop recording, free space, restart (lose the gap unless redundancy is in place).
- **Prevention:** Pre-session disk-capacity check (see [pre-session.md](pre-session.md)).

## Sync marker not visible in playback

- **Cause:** Marker outside one or more cameras' FOV, or too brief.
- **Fix:** Use a marker that is loud + bright + held for ≥1 second in the
  overlap region of all cameras' coverage.

## Fusion fails to register a camera (`add_camera` returns non-SUCCESS)

- **Cause:**
- **Fix:**
- **Prevention:** Confirm `fusion_calibration.json` contains an entry for each
  serial reported by `ZED_Explorer`. See `projection_helpers.load_extrinsics_from_fusion_conf()`.

## `[WARN] No extrinsics in fusion conf for serial …`

- **Cause:** The serial currently connected wasn't part of the last ZED360 calibration.
- **Fix:** Re-run ZED360 with the full camera set; save and point `FUSION_CONF` at the new file.

## Body tracking detects nobody

- **Cause:** Lighting, occlusion, depth-mode mismatch.
- **Fix:** Verify lighting per [hardware.md](hardware.md); try
  `DEPTH_MODE.NEURAL` and `BODY_MODEL.HUMAN_BODY_ACCURATE` as a diagnostic.
