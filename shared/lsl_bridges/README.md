# LSL bridges

> **Status:** stub
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

Custom [Lab Streaming Layer](https://labstreaminglayer.org/) outlets that
publish device timestamps (and where sensible, sample data) into LSL for
devices that don't ship native LSL support.

See [docs/time-sync.md](../../docs/time-sync.md) for the three-layer sync
architecture this fits into.

## Planned bridges

| Bridge                    | Publishes                         | Source device        | Priority | Status      |
|---------------------------|------------------------------------|----------------------|----------|-------------|
| *(integrated into recorder)* | ZED grab timestamps + camera clock (`simcenter.zed.<serial>`) | ZedBox — lives in [`multiCameraRecord.py`](../../modalities/computer-vision/code/multiCameraRecord.py) | High | **implemented** (deploy: `pip install pylsl` in ZED_env) |
| [`room_mic_marker.py`](room_mic_marker.py) | WAV capture + frame-position markers (`simcenter.mic.marker`) | Room mic / ReSpeaker XVF-3800, USB-in on analysis laptop | High | **implemented** |
| *(none needed — official)* | Live gaze → LSL via Tobii's **G3LSLConnector** (see Tobii section below) | Tobii Glasses 3 | — | External tool; not vendored |
| `bioradio_bridge.py`      | Live BioCapture stream → LSL      | BioRadio             | **Deferred** | Not planned; BioRadio deferred (see [`modalities/physiology/devices/bioradio/`](../../modalities/physiology/devices/bioradio/README.md)) |

## Bridge conventions

- One file per bridge, one outlet per bridge
- Stream name = `<repo-slug>.<device-slug>` (e.g. `simcenter.zed.frame_marker`)
- Stream type = follow LSL norms: `Markers` for timestamp-only, device-appropriate
  for numeric samples
- CLI flag `--dry-run` to print the outlet metadata and exit without publishing
- Each bridge documents its exact LSL stream schema in a header docstring

## Tobii: use the official G3LSLConnector (no custom bridge)

Tobii ships an official LSL connector with the
[Tobii.Glasses3.SDK](https://github.com/tobiipro/Tobii.Glasses3.SDK)
(.NET, Windows; precompiled binaries on the releases page). It
auto-discovers Glasses 3 units and registers an LSL outlet for the
**gaze stream**. Run it on each Tobii host laptop (dual-homed: WiFi
radio → the unit's AP; ethernet → lab LAN) and gaze appears in
LabRecorder like any other stream.

Notes:

- **License:** Tobii Pro Software Development License Agreement — *not*
  open source. Use it as a standalone external tool (same category as
  LabRecorder / EmotiBit Oscilloscope); do **not** vendor it into this
  repo. Users download it from Tobii's releases page.
- **Gaze only** — IMU, events, and scene video are not in the LSL
  stream; scene video stays on-device as always.
- **Firmware compatibility:** SDK v1.2.0 supports firmware up to 2.2.4;
  verify against the lab units before a session. Confirm the connector
  binary ships with the SDK version in use (it was confirmed on v0.7.2).
- **Dual-homed discovery:** the connector auto-locates units over the
  network; with two active interfaces, discovery can bind to the wrong
  one. If a unit isn't found, suspect this first.
- **Fallback (Tier 0):** recording on-device + Layer 1 sync markers
  (clap + flash in scene camera and recording-unit mic) works with zero
  LSL integration and remains the insurance layer regardless.

## Devices in scope for LSL

See the LSL layer table in [docs/time-sync.md](../../docs/time-sync.md#layer-2--lab-streaming-layer-lsl-for-streaming-devices).

## Devices NOT in scope

- Empatica E4 in record mode (no maintained streaming API — post-hoc
  alignment per Layer 3 in [docs/time-sync.md](../../docs/time-sync.md))

## TODOs

<!-- RESOLVED 2026-10-19: ZED frame markers implemented inside multiCameraRecord.py — a separate outlet process can't open a camera the recorder already owns, so markers are pushed from the grab loop. Recording proceeds unaffected if pylsl is absent. -->
<!-- RESOLVED 2026-10-19: room_mic_marker.py implemented (WAV via stdlib wave + sounddevice; markers map WAV frame positions to LSL time). -->
<!-- RESOLVED 2026-10: Tobii uses the official G3LSLConnector (see Tobii section above); no custom bridge. -->
<!-- TODO(unassigned): Add a shared test harness that verifies each bridge produces monotonic timestamps and expected metadata. Test outlets for loop validation live in tools/lsl_testing/. -->
