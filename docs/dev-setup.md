# Development setup

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-10-19

## What needs a Python environment (and what doesn't)

**No Python needed** — install as normal apps and run standalone:

- LabRecorder (records all LSL streams to `.xdf`)
- EmotiBit Oscilloscope (publishes EmotiBit data to LSL natively)
- Tobii Pro Eye Tracker Manager + Tobii's G3LSLConnector (publishes gaze to LSL)

**Python env needed** — anything in this repo's `shared/lsl_bridges/` or
`tools/`, plus `.xdf` verification and (later) processing pipelines.

## Analysis laptop setup (Windows)

One [uv](https://docs.astral.sh/uv/)-managed environment at the repo root:

```powershell
# one-time
winget install --id=astral-sh.uv -e

# in the repo root
uv sync
```

Run anything with:

```powershell
uv run python tools/lsl_testing/heartbeat_outlet.py
uv run python shared/lsl_bridges/room_mic_marker.py --list-devices
uv run python tools/lsl_testing/check_xdf.py path\to\session.xdf
```

Commit `pyproject.toml` and `uv.lock`; `.venv/` is gitignored.

**Troubleshooting:** if `import pylsl` complains about a missing liblsl
binary, install liblsl from the
[LSL releases page](https://github.com/sccn/liblsl/releases) and retry.
Windows wheels normally bundle it; this mostly affects other platforms.

## ZedBox (separate machine, separate env)

The ZedBox keeps its own `ZED_env` conda environment (per Stereolabs
docs) because `pyzed` is tied to the installed ZED SDK — it is **not**
managed by this repo's `pyproject.toml`. To enable LSL frame markers in
the recorder:

```bash
conda activate ZED_env
pip install pylsl
```

`modalities/computer-vision/code/multiCameraRecord.py` detects pylsl at
import time; without it, recording proceeds unchanged with a console
note.

## Heavy processing deps (deferred)

`torch`, `pyannote.audio`, `faster-whisper`, `whisperx` are intentionally
not in `pyproject.toml` yet. Add when Phase-2/4 processing work begins:

```powershell
uv add torch pyannote.audio faster-whisper
```
