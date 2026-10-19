# BioRadio

> **Status:** drafted (setup) / stub (rest)
> **Priority:** **deferred** — not planned for near-term studies
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

BioRadio is retained here as reference material for possible future use.
It is **not** part of the near-term physio stack and the broader
architecture (LSL layer, time-sync approach, host machine assignments)
should not be shaped around BioRadio's requirements. If BioRadio comes
back into scope, BioCapture runs on Windows (analysis laptop or a
dedicated Windows host) and would need either a custom LSL bridge or
Layer-3 post-hoc alignment — see [docs/time-sync.md](../../../../docs/time-sync.md).

## Hardware

- Chest-worn / belt-worn physiological transmitter (Great Lakes NeuroTechnologies)
- Companion PC software: **BioCapture**
- Bluetooth connection from BioRadio pod to host PC
- Signals (channel-configurable): GSR, ECG, RIP (respiration via chest strap), pulse oximetry (sensor pod)
- Channel layout (see [Session setup](#session-setup) for required assignments):
  - Channel 1 — GSR (**required slot**)
  - Channels 2-4 — any of RIP, ECG
  - Sensor pod (separate) — pulse oximetry

<!-- TODO(unassigned): Fill exact BioRadio model, firmware version, BioCapture version tested, supported sample rates per channel -->

## Firmware / software versions tested

<!-- TODO(unassigned): Firmware + BioCapture versions -->

## Charging

<!-- TODO(unassigned): Charging routine, expected battery life per session -->

## Electrode placement

<!-- TODO(unassigned): Diagram of standard placement for GSR electrodes, ECG leads, RIP strap, and pulse-ox sensor. Include skin-prep procedure (alcohol wipe, gel, etc.). -->

## Session setup

The procedure below is the BioCapture-driven session start. Run it _before_
the subject arrives where possible (electrode hookup excepted).

1. **Hook up electrodes** to the BioRadio unit:
   - GSR **must** be on channel 1.
   - RIP (chest strap) and ECG go on any of channels 2-4.
   - Pulse ox plugs into the sensor pod below the unit.
2. **Click _Connect_** in BioCapture.
   - It should auto-connect. If not: verify Bluetooth is enabled on the PC,
     then power-cycle the BioRadio pod.
3. **Click _Device Config_** in BioCapture:
   - Select the appropriate sensor for each channel (GSR on 1, etc.).
   - Edit the text labels to match any changes — these labels appear on the
     live data feed.
   - Confirm the checkbox is selected for every channel in use.
   - Click _Program device_.
4. In the **_Hide data feeds_** dropdown, hide all _Accel_ and _Gyro_
   streams (unless explicitly needed for the session).
5. **Start acquisition** by clicking the green triangle (_Start data acquisition_).
6. For each visible stream, right-click and select
   **_Y axis → Scale continuous_** so the y-axis auto-fits.
7. Set **_Time scale_** to your preference (typically 10 s).
8. Set **_View → Time scale_** to either elapsed or real time.
   - This matters for **exported data**: only the selected option appears in
     the exported file. Decide before recording — changing mid-session
     affects what reaches disk.

After setup, follow the cross-device session SOP at
[../../during-session.md](../../during-session.md).

## Time sync

<!-- TODO(unassigned): BioCapture's clock-set behavior, drift characteristics, sync-marker approach (does BioCapture support an event marker? If not, use accelerometer-detectable physical marker per docs/time-sync.md). -->

## Data offload

- Files produced: <!-- TODO -->
- Filename conversion to project convention (per [docs/identifiers.md](../../../../docs/identifiers.md)): <!-- TODO -->

## Known issues

<!-- TODO(unassigned): Populate as encountered. Likely candidates: lead pop-off during high-activity scenarios, Bluetooth dropouts at range, BioCapture crashes mid-session and recovery procedure. -->
