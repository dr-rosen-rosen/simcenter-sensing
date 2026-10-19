# Time synchronization across modalities

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

Multimodal analysis lives or dies on accurate time alignment. This document
describes the **three-layer sync architecture** used across every session,
plus per-modality references for streams that participate in each layer.

## Canonical clock

One host machine, running NTP against a reliable time source (institution
NTP > `pool.ntp.org`), is chosen as the **canonical clock** for each
session. Every device sync procedure is performed against this host, and
LabRecorder (Layer 2, below) runs on it so LSL clock offsets are measured
against it directly.

Record the canonical host + timezone in the run sheet.

## The three layers

### Layer 1 — Human sync markers at session boundaries (unkillable insurance)

A deliberate, multimodal-detectable event captured at session start and
session end against the canonical clock. This is the **ground truth** if
streaming fails or a device crashes.

Recommended marker: **hand clap + visible flash** (LED, flash card, or
bright object waved in front of every camera).

Requirements:

- Visible in every camera's field of view (CV, eye-tracking scene camera)
- Detectable in every audio channel (comms mic, eye-tracker recording-unit mic)
- Detectable on wrist-worn accelerometry — the clap creates a clear IMU
  signature on the clapping wrist for E4 / EmotiBit
- Timestamped against the canonical clock in the run sheet

Run at session **start** and **end**, plus after any mid-session device
disconnect/reconnect. Cheap; unkillable; **never skip, even when Layer 2
is running.**

### Layer 2 — Lab Streaming Layer (LSL) for streaming devices

For devices that produce a live stream, [Lab Streaming Layer](https://labstreaminglayer.org/)
provides sub-millisecond clock sync across streams and machines without you
writing any of that code. LabRecorder produces one `.xdf` per session
containing every subscribed stream with **per-stream clock-corrected
timestamps**.

Devices in the LSL layer:

| Device            | LSL outlet                                | Bridge required?                                  |
|-------------------|--------------------------------------------|---------------------------------------------------|
| EmotiBit          | Native (in EmotiBit Oscilloscope)          | None                                              |
| Room mic (comms)  | Timestamped marker stream (audio to WAV)   | Small custom outlet — see `shared/lsl_bridges/`   |
| ZED / ZedBox      | Frame timestamps only; video stays in SVO2 | Small custom outlet — see `shared/lsl_bridges/`   |
| Tobii Glasses 3   | Live gaze via Tobii's official **G3LSLConnector** (Windows/.NET) | None — external tool from the [Glasses 3 SDK releases](https://github.com/tobiipro/Tobii.Glasses3.SDK/releases); see `shared/lsl_bridges/` |

Devices that **do not** participate in LSL:

- **Empatica E4 in record mode** — no maintained streaming API; use Layer 3.
- **BioRadio** — deferred, not on near-term roadmap (see [`modalities/physiology/devices/bioradio/`](../modalities/physiology/devices/bioradio/README.md)). If reactivated, would either need a custom BioCapture bridge or Layer-3 post-hoc alignment.
- Any offline recorder without a live interface.

See [`shared/lsl_bridges/`](../shared/lsl_bridges/README.md) for the
outlets we ship (or plan to ship).

### Layer 3 — Post-hoc alignment for record-then-download devices

For devices that write to internal storage and are downloaded after the
session (E4, ZED SVO2 video, standalone recorders), alignment happens
after the fact using the Layer 1 human markers plus per-device clock offsets.

Procedure per device:

1. Read the device's own clock offset from canonical at fit time _and_ at
   unfit time (both recorded in the run sheet).
2. Detect the Layer 1 human marker in the device's data (algorithmically
   where possible; manually where not).
3. Fit a linear drift model between canonical clock and device clock.
4. Rewrite device timestamps into canonical-clock time.

Automation for steps 2-4 lives (or will live) in `shared/time_sync/`.

## Practical LSL notes

- **Start LabRecorder before the session begins** and let all outlets
  connect for **30-60 seconds** so clock offsets stabilize. Short test
  recordings have noisy offset estimates — this bites people during
  quick tests but is not a problem for real sessions.
- **Video stays out of LSL.** LSL is a numeric-stream bus; video buffers
  would overflow. Publish frame timestamps as an LSL marker stream and
  keep SVO2 / mp4 files on disk.
- **One `.xdf` per session.** Match the filename to the session ID from
  [identifiers.md](identifiers.md):

  ```
  <study>_<subject-or-team>_<session>[_<run>].xdf
  ```

- `pyxdf` loads `.xdf` into Python; loaders also exist for MATLAB, R, C++.
- LSL clock corrections in `.xdf` are **already applied** to timestamps
  when loaded via pyxdf — you don't apply them again.

## Verification

After each session, `shared/time_sync/verify_session.py` (TODO) will:

- Detect Layer 1 markers in each modality
- Report residual offset (canonical → each device) and drift rate
- Emit an HTML sync report to the session's `reports/` directory

The sync report is reviewed before data enters the derived pipeline.

## Hardware trigger box (optional upgrade path)

For labs needing <1 ms alignment on scenario-start events, a hardware
trigger box (TTL or audio-pulse fanout) is worth adding _on top of_ LSL.
Not part of the current architecture; documented here as a known upgrade
path if precision requirements tighten.

## Per-device sync procedures

Cross-references to modality-specific sync details:

- Computer vision (ZED): [modalities/computer-vision/pre-session.md](../modalities/computer-vision/pre-session.md)
- Physiology:
  - Empatica E4: [modalities/physiology/devices/empatica-e4/README.md](../modalities/physiology/devices/empatica-e4/README.md)
  - EmotiBit: [modalities/physiology/devices/emotibit/README.md](../modalities/physiology/devices/emotibit/README.md)
  - BioRadio: [modalities/physiology/devices/bioradio/README.md](../modalities/physiology/devices/bioradio/README.md)
- Eye tracking (Tobii Glasses 3): [modalities/eye-tracking/pre-session.md](../modalities/eye-tracking/pre-session.md)
- Communication (room mic): [modalities/communication/README.md](../modalities/communication/README.md)

## TODOs

<!-- TODO(unassigned): Build shared/time_sync/verify_session.py — auto-detect Layer 1 markers per modality, fit drift, produce HTML report -->
<!-- TODO(unassigned): Prototype LSL bridges in shared/lsl_bridges/ — start with ZED frame markers and room mic (smallest scope, biggest coverage win) -->
<!-- RESOLVED 2026-06: Tobii ships an official G3LSLConnector with the Glasses 3 SDK (Windows/.NET, gaze stream). See shared/lsl_bridges/README.md for usage notes and caveats. -->
<!-- TODO(unassigned): Verify G3LSLConnector against lab units — firmware compatibility (SDK v1.2.0 supports up to 2.2.4) and discovery behavior on a dual-homed host laptop -->
<!-- TODO(unassigned): Migrate canonical drift-modeling helpers from tpd's 1_funcs_generic.R when Layer 3 utilities are built -->
<!-- TODO(unassigned): Update per-device README pages (CV pre-session, physio devices, ET pre-session) with the specific LSL layer / Layer 3 procedure that applies to each -->
