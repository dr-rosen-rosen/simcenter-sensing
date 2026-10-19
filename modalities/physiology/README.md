# Physiology

> **Status:** stub
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## Scope

Wearable-sensor capture of autonomic-nervous-system signals during simulation
sessions: heart rate and HRV, electrodermal activity, skin temperature,
accelerometry, and (depending on device) respiration and ECG.

## Devices

| Device         | Signals                                | Wear location | Priority     | Subdir |
|----------------|-----------------------------------------|---------------|--------------|--------|
| Empatica E4    | BVP, EDA, skin temp, 3-axis accel       | Wrist         | Active       | [devices/empatica-e4/](devices/empatica-e4/README.md) |
| EmotiBit       | PPG, EDA, skin temp, 3-axis IMU, more   | Wrist / chest | Active       | [devices/emotibit/](devices/emotibit/README.md) |
| BioRadio       | GSR, ECG, RIP (respiration), pulse ox   | Chest + pod   | **Deferred** | [devices/bioradio/](devices/bioradio/README.md) |

**BioRadio is deferred** — not planned for near-term studies. Setup notes
are retained under `devices/bioradio/` as reference for possible future
use, but the architecture and processing pipelines should not be shaped
around BioRadio's requirements.

## Cross-device material

Sections below cover material common to running a physio session with any
combination of devices. Device-specific details live under `devices/`.

| Section          | File                                       | Status      |
|------------------|--------------------------------------------|-------------|
| Pre-session      | [pre-session.md](pre-session.md)           | stub        |
| During-session   | [during-session.md](during-session.md)     | stub        |
| Troubleshooting  | [troubleshooting.md](troubleshooting.md)   | stub        |
| Processing       | [processing.md](processing.md)             | stub        |
| Data spec        | [data-spec.md](data-spec.md)               | stub        |

## TODOs for collaborators

<!-- TODO(unassigned): Triage existing physio notes and code; this is a high-priority Phase 1 effort -->

- [ ] Identify canonical sync code (see [tpd's `1_funcs_generic.R`](../../docs/storage.md)) and migrate / link from `shared/`
- [ ] Draft per-device fitting protocols (E4, EmotiBit)
- [ ] Document multi-device time-sync routine (clocks across E4 + EmotiBit)
- [ ] Capture known-failure catalog from Joplin notes and prior studies
- [ ] Define derived feature schema (HR, HRV bands, EDA tonic/phasic, etc.)
