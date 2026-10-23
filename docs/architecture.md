# System architecture

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

The higher-level view of how the sim-center sensing system is organized
during data collection: which machines exist, what runs where, how
they're networked, and how data flows from capture to storage.

For time-alignment specifics see [time-sync.md](time-sync.md). For
modality-specific details see the per-modality READMEs under
`modalities/`.

## Design principles

Three decisions define the shape of everything else.

1. **One canonical clock.** The Windows analysis laptop is the reference
   clock; LabRecorder runs on it; every device sync happens against it.
   See [time-sync.md](time-sync.md).
2. **Heavy compute lives on the analysis laptop.** Diarization, ASR, CV
   pose extraction, and physio feature extraction are all analysis-laptop
   jobs, offline by default. Edge devices (ZedBox) do only what they must
   do live — record video, publish frame markers to LSL.
3. **Local lab network, not hospital network.** A dedicated lab router
   avoids hospital-IT approvals, RADIUS auth, and network-onboarding
   friction. Internet uplink is not required for a session.

## Topology

```
                    ┌─────────────────────────────────┐
                    │  Lab Router (WiFi + Ethernet)   │
                    │  No internet uplink required    │
                    └──┬───────────────────────┬──────┘
                       │ Ethernet              │ WiFi
        ┌──────────────┴──────────┐            │
   ┌────▼────────────────┐  ┌─────▼──┐         │
   │ Analysis Laptop     │  │ ZedBox │         │
   │ Windows + Nvidia    │  │        │         │
   │                     │  │ SVO2 → │         │
   │ - Canonical clock   │  │  SSD   │         │
   │ - LabRecorder       │  │        │         │
   │ - Room mic (USB in) │  │ Frame- │         │
   │ - pyannote/whisper  │  │ marker │         │
   │ - Offload target    │  │  LSL   │         │
   └─────────────────────┘  └────────┘         │
                                               │
                    ┌──────────────────────────┼────────────┐
                    │                          │            │
              ┌─────▼────────┐         ┌───────▼──────┐  ┌──▼──────────┐
              │ Tobii unit 1 │         │ Tobii unit 2 │  │ EmotiBit(s) │
              │ + laptop     │         │ + laptop     │  │ Native LSL  │
              │ (own AP)     │         │ (own AP)     │  │ over WiFi   │
              └──────────────┘         └──────────────┘  └─────────────┘
```

Three wired nodes (analysis laptop, ZedBox, and if used any Windows host
for BioCapture) plus mobile devices on WiFi. Each Tobii Glasses 3 unit
hosts its own access point; its dedicated host laptop joins that unit's
network directly, not the lab LAN (see [Network specifics](#network-specifics)).

## Machine roles

| Machine                    | Role                                                                                       | Connection                              |
|----------------------------|--------------------------------------------------------------------------------------------|-----------------------------------------|
| **Analysis laptop**        | Canonical clock; LabRecorder; room-mic capture; all processing (CV, diarization, ASR)      | Ethernet to lab router                  |
| Windows, Nvidia GPU        | See [time-sync.md](time-sync.md), [modalities/communication/processing.md](../modalities/communication/processing.md), [modalities/computer-vision/processing.md](../modalities/computer-vision/processing.md) |                                          |
| **ZedBox**                 | Record SVO2 to onboard SSD; publish frame timestamps as LSL outlet                          | Ethernet to lab router                  |
| Ubuntu, edge compute       | See [modalities/computer-vision/](../modalities/computer-vision/README.md)                  |                                          |
| **Tobii host laptops** (up to 2) | Control their unit over its AP; run Tobii's official **G3LSLConnector** (Windows/.NET) to publish live gaze into LSL (see [`shared/lsl_bridges/`](../shared/lsl_bridges/README.md)) | Ethernet to lab router **+** WiFi radio to the unit's AP |
| Any OS                     | See [modalities/eye-tracking/pre-session.md](../modalities/eye-tracking/pre-session.md)     |                                          |
| **EmotiBit host**          | Runs EmotiBit Oscilloscope, which publishes native LSL                                     | WiFi client on lab network              |
| Any laptop or Pi           | See [modalities/physiology/devices/emotibit/](../modalities/physiology/devices/emotibit/README.md) |                                     |
| **Lab router**             | Local LAN + WiFi. No internet uplink required.                                             | -                                        |

## Network specifics

**Lab router.** A dedicated router (GL.iNet Beryl / Slate class, or any
dual-band travel router) provides:

- WiFi SSID for mobile devices (EmotiBit)
- Ethernet ports for wired devices (analysis laptop, ZedBox)
- Static-IP scheme so machines are discoverable by hostname
- No internet uplink required — the network is closed to the session

**Wire what you can.** Ethernet is more reliable than WiFi for anything
sitting on a shelf. Analysis laptop, ZedBox, and any spare Windows host
should be wired. WiFi only for devices that require it.

**Tobii WiFi.** Each Tobii Pro Glasses 3 recording unit hosts its own AP
(SSID format `TG03B-XXXXXXXXXX`, factory default password `TobiiGlasses`
— see [modalities/eye-tracking/hardware.md](../modalities/eye-tracking/hardware.md)).
The Tobii host laptop joins that unit's AP directly, not the lab LAN.
For 2-unit sessions this means 2 host laptops, each dedicated to one
unit. If Tobii firmware supports **client mode** (each unit joining the
lab LAN as a client), that would collapse both onto the lab LAN and
reduce laptop count — worth verifying against your current firmware.

## Compute placement

| Stream / job                        | Where it runs                        | Why                                       |
|-------------------------------------|--------------------------------------|-------------------------------------------|
| ZED SVO2 recording                  | ZedBox                               | Video stays local; disk I/O only          |
| ZED frame-marker LSL outlet         | ZedBox (small script)                | Publishes timestamps only, not video      |
| CV pose extraction (post-session)   | Analysis laptop                      | Needs Nvidia GPU; not live-critical       |
| CV pose extraction (live, optional) | ZedBox                               | Only if a live dashboard needs it         |
| Tobii gaze processing               | Tobii recording unit (on-glasses)    | Vendor handles it                         |
| EmotiBit sampling                   | EmotiBit hardware                    | Onboard sensor                            |
| EmotiBit LSL publishing             | EmotiBit host (any machine)          | Light task                                |
| Room mic capture + WAV write        | Analysis laptop (USB in)             | Simplest path; no extra host              |
| Room mic LSL outlet                 | Analysis laptop                      | Same process as capture                   |
| Diarization + ASR (post-session)    | Analysis laptop                      | GPU load; batch by default                |
| Diarization + ASR (near-realtime)   | Analysis laptop                      | Same code, chunked 5-30 s hops            |
| LabRecorder                         | Analysis laptop                      | Because it's the canonical clock host     |
| Session offload                     | Analysis laptop is the destination   | See [ZedBox offload](#zedbox-offload-workflow) |

**One workhorse, several capture nodes.** The analysis laptop does
essentially everything computationally interesting. Other machines are
capture-and-forward nodes. This is the right shape given you have one
strong GPU machine.

## Data flow per session

```
[before session]
    Start lab router
    Start analysis laptop; sync clock via NTP
    Start LabRecorder; verify each outlet connects (30-60 s wait for LSL offsets to stabilize)
    Boot ZedBox; verify frame-marker outlet connects to LabRecorder
    Boot Tobii units; each host laptop joins its unit's AP
    Boot EmotiBit(s); verify they publish to LSL
    Plug in room mic; verify audio input on analysis laptop

[during session]
    Capture opening sync marker (clap + flash) — Layer 1 unkillable
    ZedBox records to local SSD; publishes frame markers to LSL
    Tobii records to on-glasses SD; can also stream (optional)
    EmotiBit publishes samples to LSL
    Room mic writes WAV + publishes markers to LSL
    LabRecorder writes one .xdf capturing all LSL streams
    Capture closing sync marker

[post session — same day]
    Verify sync report (Layer 1 markers detectable in every stream)
    Offload ZedBox SVO2 files to analysis laptop (see below)
    Offload Tobii recordings (SD pull or WiFi download)
    Move .xdf + WAV + offloaded raws into the session directory per docs/storage.md

[post session — later]
    Run processing pipelines: CV pose, diarization + ASR, physio features
    Produce derived data + QA reports
    Move raw + derived to long-term storage (see below)
```

## ZedBox offload workflow

ZedBox is Ubuntu, analysis laptop is Windows. Simplest reliable path:

1. **Windows OpenSSH server** running on the analysis laptop (native to
   modern Windows; a couple of clicks in Optional Features).
2. **Operator-triggered rsync** on the ZedBox after each session:

   ```bash
   rsync --progress --checksum --remove-source-files \
       ~/zed_rec/ user@analysis-laptop:/sessions/<session-id>/cv/
   ```

3. **Delete-after-verify.** `--checksum` verifies each file after
   transfer; `--remove-source-files` removes source only on successful
   copy. ZedBox SSD becomes a rotating buffer.
4. **Session-level directory structure** on the analysis laptop mirrors
   [docs/storage.md](storage.md). One session = one directory.

The ZedBox SSD holds multiple sessions if offload is deferred, but the
discipline of same-day offload keeps the "one-session-per-directory"
structure clean and reduces recovery scope if something goes wrong.

<!-- TODO(unassigned): Ship an `offload_session.sh` wrapper on the ZedBox that pulls the session ID interactively, runs the rsync, verifies checksums, and writes a manifest. Lives in modalities/computer-vision/code/ or shared/. -->

## Storage tiering

Long-term storage is a real open issue. Pragmatic tiering while
institutional storage is being sorted out:

| Tier      | Where                                                    | Cost              | Notes                                                       |
|-----------|----------------------------------------------------------|-------------------|-------------------------------------------------------------|
| **Short** | Large external SSD attached to analysis laptop           | ~$150-300 (2-4 TB) | Unblocks recording immediately; not a real archive          |
| **Medium**| Small lab NAS (e.g., Synology 4-bay + 2× 12 TB, RAID)    | ~$1.2 k           | 12 TB usable, redundant, mountable from any lab machine     |
| **Long**  | Institutional research storage                           | Institutional     | Start the conversation now; onboarding is slow              |
| **Never** | Consumer cloud (Dropbox, Google Drive personal)          | -                 | PHI-adjacent; institution-approved cloud only               |

Institutional cloud (Box for research, S3-behind-BAA, etc.) is fine
where it's institution-approved and covered by IRB. The **never** row
is about consumer/personal cloud — a common accident, hard to reverse.

<!-- TODO(unassigned): Track long-term storage decision here as it evolves. Update docs/storage.md with the concrete path names once institutional storage lands. -->

## Validation sequence (status as of 2026-10-19)

1. ✅ **Lab router** — Linksys WRT120N configured (`simlab`, WPA2, DHCP,
   no WAN); analysis laptop wired; EmotiBit on WiFi. ZedBox wiring
   pending its next availability.
2. ✅ **LSL loop** — heartbeat + keyboard-marker outlets captured by
   LabRecorder; `.xdf` verified with `tools/lsl_testing/check_xdf.py`.
3. ✅ **ZedBox** — validated 2026-10-21: liblsl via GitHub arm64 deb
   (conda-forge has no linux-aarch64 build) + `pip install pylsl` in
   ZED_env; `simcenter.zed.44429816` markers recorded across the LAN
   (~1/s, counts matching mic/heartbeat). SVO2 written locally as
   designed. Note: ZedBox on the lab LAN has no internet by design —
   software installs happen over a temporary hotspot with the ethernet
   unplugged (wired route otherwise wins and DNS dead-ends at the
   router). Open item: confirm second camera (45817796) publishes its
   own stream when connected.
4. ✅ **EmotiBit** — 15 continuous + 4 derived streams over the lab LAN,
   effective rates ~nominal, clap markers captured (validated 2026-10-19,
   145 s and 336 s recordings).
5. ✅ **Mic array** — ReSpeaker XVF3800 (USB v2.1.1 `16k6ch` firmware):
   6-ch @ 16 kHz via `room_mic_marker.py`, WAV + 1 Hz markers wall-to-wall
   in the overlap window (validated 2026-10-19). Use the WASAPI device
   entry on Windows.
6. ✅ **Tobii** — G3LSLConnector v1.2.0 against firmware 1.29.4
   (validated 2026-10-21): dual-homed discovery worked (lab laptop on
   ethernet + unit's AP simultaneously); Gaze2d/3d, GazeDirection,
   GazeOrigin, Pupil at ~50 Hz co-recorded with EmotiBit + mic.
   Gotchas: run exactly ONE connector instance (each publishes its own
   outlet set — two instances = duplicate live streams); the connector's
   IMU outlets register but carry no data (leave unchecked); the unit's
   web UI has an **ethernet section** — wiring the recording unit to the
   lab router via USB-C adapter is the preferred path to multi-unit
   setups (untested; try before buying a second host laptop).

All six steps validated individually (2026-10-21). Remaining capstone:
a **full-system rehearsal** — every stream live in one recording (ZED +
EmotiBit + mic + Tobii + claps) with a verified common overlap window.

## Orchestration & data management — requirements backlog

Accumulated from the October 2026 validation sessions; this is the next
build phase. Each item earned its place by biting us at least once.

**Session orchestration (`tools/session_orchestrator` — core built
2026-10-23, tested against synthetic streams; Windows/lab adaptation
pending, see its README):**

- Preflight: every expected stream present **and flowing** before Start —
  LabRecorder records checked-but-dead streams as empty tracks without
  complaint (EmotiBit off, Tobii battery dead → silent empty data).
- Preflight: each stream present **exactly once** — a stale
  G3LSLConnector instance produced duplicate live copies of every Tobii
  stream.
- Single-command start/stop via LabRecorder's remote-control interface,
  with filenames from [identifiers.md](identifiers.md) (not
  `sub-P001/.../run-006`, which caused a wrong-file analysis).
- Post-stop: auto-run `check_xdf`, write a session manifest (streams,
  counts, overlap window, device inventory, operator notes).
- Battery/charge state is part of preflight culture: devices live on a
  charging shelf between sessions (two sessions lost time to dead
  Tobii / misconfigured EmotiBit).
- **Tobii session start is two machine actions + one human step.** The
  G3LSLConnector's live gaze stream runs independently of on-device
  recording (validated 2026-10-21: gaze streamed with no recording
  active) — but **scene video + the full dataset exist only if an SD
  recording is started on the unit**, and the Layer-1 clap only reaches
  the Tobii modality via the scene camera. Orchestrator must: start the
  connector, start an on-device recording via the G3 HTTP API
  (g3pylib wraps it), and gate on per-wearer calibration
  (human-in-the-loop; success is API-verifiable). The capstone
  rehearsal must include the SD recording.

**Data management:**

- ✅ ZED SVO2 overwrite hazard — **fixed in code 2026-10-21**:
  `multiCameraRecord.py` now writes each run into a timestamped
  subdirectory (`~/zed_rec/<YYYYMMDD-HHMMSS>/<serial>.svo2`). A fixed
  per-serial path silently overwrote the prior session. *Deploy note:
  ZedBox needs a `git pull` (over hotspot, ethernet unplugged) to pick
  this up.*
- `offload_session.sh` (ZedBox → lab laptop rsync, verify-then-delete) —
  still TODO; requires enabling OpenSSH server on the lab laptop.
- External SSD for the lab laptop (raw-session tier) — purchase pending;
  real sessions start accumulating GBs the moment ZED video joins.
- **Tobii recording offload** — scene video + full dataset live on the
  unit's SD card (rotating buffer, same policy as the ZedBox SSD:
  delete only after verified copy). Preferred path: automated
  per-session HTTP download from the unit via the G3 API (faster if the
  wired-ethernet option pans out; slow but workable over the unit's
  AP). Defined manual fallback: SD-card pull. Lands in the session
  directory per [storage.md](storage.md).
- Session directory layout per [storage.md](storage.md), with the
  manifest as its index.

## Related documentation

- [time-sync.md](time-sync.md) — three-layer sync architecture (Layer 1
  human markers, Layer 2 LSL, Layer 3 post-hoc)
- [storage.md](storage.md) — session directory layout, naming
- [identifiers.md](identifiers.md) — subject/session/run IDs
- [data-governance.md](data-governance.md) — PHI, retention, consent
- Per-modality READMEs under `../modalities/`
- LSL bridge inventory under [`../shared/lsl_bridges/`](../shared/lsl_bridges/README.md)
- [session-console.md](session-console.md) — Open MCT live session console / post-session review (evaluated 2026-10-13; post-capture-validation layer)

## Explicitly deferred

- **BioRadio** integration is not on the near-term roadmap; see
  [modalities/physiology/devices/bioradio/README.md](../modalities/physiology/devices/bioradio/README.md).
  If it comes back into scope, BioCapture (Windows) runs on the analysis
  laptop and would need a custom LSL bridge (or Layer-3 post-hoc alignment).

## TODOs

<!-- TODO(unassigned): Verify Tobii Pro Glasses 3 client-mode support against current firmware; if supported, update the network section to collapse Tobii onto the lab LAN -->
<!-- TODO(unassigned): Ship an `offload_session.sh` wrapper on the ZedBox (see above) -->
<!-- TODO(unassigned): Track long-term storage decision; update once institutional storage lands -->
<!-- TODO(unassigned): Once first pilot runs, update the validation sequence with concrete measured offset/drift numbers so new collaborators have a benchmark -->
