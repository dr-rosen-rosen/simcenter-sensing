# Session runbook — operator manual

> **Status:** drafted (living document — fix it every time reality disagrees)
> **Owner:** unassigned
> **Last reviewed:** 2026-11-05

Step-by-step bring-up for a data-collection session, in order. Each block
ends with a **Verify** line; don't move on until it passes. "If not"
entries are real failures we've hit, not hypotheticals.

**Bring-up order:** infrastructure → EmotiBit → mic → ZedBox → Tobii →
console → record → teardown.

---

## 0. Infrastructure

1. Lab router powered (SSID `simlab`).
2. Lab laptop wired to a numbered LAN port.
3. Open LabRecorder; confirm remote control (RCS) is enabled, port 22345.

**Verify:** `ipconfig` shows the Ethernet adapter on `192.168.1.x`.
**If not:** numbered port (never the Internet port); reseat; ~30 s for DHCP.

Devices should come off the charging shelf charged. Battery casualties
have cost us two sessions.

---

## 1. EmotiBit

1. Power switch on. It joins `simlab` automatically (credentials in
   `config.txt` on its SD card — `simlab` must be FIRST in the list).
2. Launch **EmotiBit Oscilloscope** on the lab laptop.
3. Select the EmotiBit when it appears in the device list; connect.
4. Enable **LSL output** in Oscilloscope's output settings.

**Verify:** signals drawing in Oscilloscope; after **Update** in
LabRecorder, ~15 streams (`PPG_IR`, `PPG_RED`, `PPG_GRN`, `EDA`, `TEMP1`,
`THERM`, `ACC_*`, `GYRO_*`, `MAG_*`) plus derived (`HR`, `SCR_*`).

**If not:**
- **Red LED** = low battery → charge.
- Not in Oscilloscope's list → check the router's DHCP table
  (`http://192.168.1.1` → Status → Local Network → DHCP Clients Table).
  Absent there = it's chasing a different WiFi → fix `config.txt` order
  on the SD card (power off, pop card, edit, reinsert).
- On the DHCP table but not in Oscilloscope → restart Oscilloscope
  (it binds network interfaces at startup; this bites especially after
  joining the Tobii AP — bring EmotiBit up BEFORE joining Tobii WiFi,
  or restart Oscilloscope after).

---

## 2. Mic array (ReSpeaker XVF3800)

1. Plug into the lab laptop: **the XMOS USB-C port (near the 3.5 mm
   jack)**, data cable. The other USB-C port is the XIAO's — it dings
   but is not audio.
2. Find the device index — **it shifts between reboots, always re-check**:

   ```
   uv run python shared/lsl_bridges/room_mic_marker.py --list-devices
   ```

   Use the **Windows WASAPI** row showing **(6 in, 0 out)**.
3. Start capture (fill in the index and session-appropriate filename):

   ```
   uv run python shared/lsl_bridges/room_mic_marker.py --device <idx> --samplerate 16000 --out <session>_audio.wav
   ```

**Verify:** banner says 6 channels @ 16000; `simcenter.mic.marker` in
LabRecorder after Update; WAV file growing on disk.

**If not:** device absent from the list entirely → wrong USB-C port or
charge-only cable; if it has never enumerated on this machine, see the
firmware section in `modalities/communication/hardware.md` (unit must run
the USB 16k6ch firmware, not I2S).

---

## 3. ZedBox

1. Power on; ethernet to a numbered router port. (The ZedBox has no
   internet on the lab LAN **by design** — software installs happen over
   a phone hotspot with the ethernet unplugged.)
2. At its console:

   ```
   conda activate ZED_env
   cd ~/simcenter-sensing/modalities/computer-vision/code
   python multiCameraRecord.py
   ```

3. Note the printed **session output dir** (timestamped, one per run) and
   per-camera lines: `recording to ...` + `LSL frame markers on`.

**Verify:** `simcenter.zed.<serial>` in LabRecorder, one per connected
camera.

**If not:**
- `pylsl not installed` → `ZED_env` not activated.
- `No ZED devices found` → camera USB/cabling.
- One camera missing → look for `[<serial>] open failed` in its console.

---

## 4. Tobii Glasses 3

1. Battery into the recording unit; glasses cabled to it; **hold** power
   until boot.
2. Lab laptop joins the unit's WiFi (`TG03B-XXXXXXXXXX`, password is the
   Tobii factory default) — **ethernet stays plugged**; the laptop is on
   both networks at once. Bring up one unit at a time.
3. **Close ALL G3LSLConnector windows, then start exactly one.** Two
   instances = every gaze stream duplicated live (seen 2026-10-21).
4. It auto-discovers the unit and registers the gaze outlets.
5. **Real sessions only (not stream tests):** also start an **on-device
   SD recording** (web UI at the WiFi adapter's gateway IP) — scene
   video exists ONLY if recording — and **calibrate the wearer**.

**Verify:** `Gaze2d`, `Gaze3d`, `GazeDirection`, `GazeOrigin`, `Pupil`
each appear **exactly once** in LabRecorder — and **someone must be
wearing the glasses**: the gaze streams carry no data without eyes in
front of the cameras (learned 2026-11-05). Empty-while-unworn is normal,
not broken. This also means the orchestrator preflight needs the wearer
fitted BEFORE it runs, or its gaze flow-checks will fail honestly.

**If not:**
- Streams registered but no data → is anyone wearing the glasses?
- Each stream twice → stale connector; close all, start one.
- Unit not discovered → confirm the laptop actually joined the right
  `TG03B-*` network; restart the connector (fixes most streaming issues).
- Connector crashing / WiFi dropping → reconnect the laptop to the
  unit's AP first, then restart the connector (in that order); it is
  sensitive to the WiFi link breaking underneath it.
- Unit dead → battery (hold power to confirm); swap + charge.

---

## 5. Session console (optional, any time after step 0)

```
uv run python tools/session_console/adapter.py
```

Browse `http://localhost:8300`. Streams appear as devices come up.
"Port already in use" → an adapter is already running
(`pkill`/Task-Manager it, or just use the one that's running).

---

## 6. Record

**Orchestrated (preferred):**

```
uv run python tools/session_orchestrator/orchestrate.py run --unit <T###> --profile tools/session_orchestrator/profiles/lab.toml
```

Preflight gates on everything above being present-exactly-once-and-
flowing. Type labels at the `mark>` prompt to annotate; `stop` ends.
Verification + manifest are automatic.

**Manual fallback:** LabRecorder → Update → check streams → filename →
Start. Stop with the Stop button and LET IT FINISH (killing it corrupts
the file tail).

**Either way — Layer 1 sync markers:** clap + flash at session start AND
end, visible to cameras, audible to mic, near the EmotiBit wrist, with a
matching `clap` marker typed at the prompt.

---

## 7. Teardown + data

1. Stop recording (orchestrator `stop`, or LabRecorder Stop button).
2. Ctrl+C the mic script (prints duration) and ZedBox recorder (prints
   frame count); stop the Tobii SD recording.
3. **Offload** (rotating-buffer rule everywhere: delete only after
   verified copy):
   - ZedBox → `./offload_session.sh` (verifies SHA-256 remotely; see
     script header for one-time Windows OpenSSH setup).
   - Tobii → SD card pull or HTTP download from the unit.
   - Mic WAV + `.xdf` + manifest → session directory per
     `docs/storage.md`.
4. Everything back on the charging shelf.
