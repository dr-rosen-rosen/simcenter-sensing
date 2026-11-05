# Session orchestrator

> **Status:** drafted — core loop built + tested against synthetic streams (2026-10-23);
> Windows/lab adaptation pending
> **Owner:** unassigned

One-command session management: preflight → record → annotate → verify →
manifest. Built against the requirements backlog in
[docs/architecture.md](../../docs/architecture.md) — every check exists
because its absence cost us a session during October 2026 validation.

## What it does

```
orchestrate.py run --unit T001 --run 1
```

1. **Preflight** — resolves LSL streams and checks each expected stream is
   present, present **exactly** the expected number of times (catches stale
   duplicate connectors), and actually **flowing** (catches dead devices —
   LabRecorder records checked-but-dead streams as empty tracks without
   complaint). Aborts on failure unless `--force`.
2. **Record** — drives LabRecorder via its remote-control socket (port
   22345): refresh, select all, set filename, start. Filenames follow
   [docs/identifiers.md](../../docs/identifiers.md):
   `<study>_<unit>_<YYYYMMDD-HHMM>[_Rnn]_lsl.xdf` under
   `out_dir/<study>/<unit>/<session>/`.
3. **Annotate** — lines typed at the `mark>` prompt publish LSL markers on
   `simcenter.orchestrator` (so they land **in the recording**) and are
   logged to the manifest. `stop` ends the session.
4. **Verify + manifest** — runs the `check_xdf` analysis on the recording
   and writes `<stem>_manifest.json` beside it: session metadata, operator,
   preflight evidence, annotated events, verification summary.

The orchestrator is **never on the capture-critical path**: if it dies
mid-session, LabRecorder keeps recording.

## Files

| File | Purpose |
|---|---|
| `orchestrate.py` | The orchestrator (`preflight` and `run` subcommands) |
| `profiles/default.toml` | Expected-stream profile matched to the simulator |
| `simulate_devices.py` | Synthetic device streams for hardware-free testing; `--drop NAME` fakes a dead device, `--dup NAME` fakes a stale duplicate connector |
| `mock_labrecorder.py` | Logs RCS commands; protocol testing without LabRecorder |

## Testing without hardware (any machine)

Terminal 1: `python simulate_devices.py`
Terminal 2: `python mock_labrecorder.py`
Terminal 3: `python orchestrate.py run --unit T001`

On macOS, pylsl needs liblsl; the scripts auto-use
`~/.local/lib/liblsl.dylib` if present (extract from the
[liblsl release .pkg](https://github.com/sccn/liblsl/releases) via
`pkgutil --expand-full` and ad-hoc re-sign: `codesign -f -s -`).

## Lab deployment (pending — next lab visit)

- [x] **LabRecorder remote control** — verified on real hardware
      2026-11-05. Note: the destination must be sent as
      `filename {root:<dir>} {template:<name>}`; an absolute path in
      template alone is silently ignored.
- [x] **`profiles/lab.toml`** — written from the validated October stream
      inventory; confirmed against the live rig 2026-11-05. Reminder:
      gaze flow-checks need the glasses ON a wearer during preflight.
- [x] **Windows pass** — orchestrated end-to-end run on the lab laptop
      2026-11-05 (correct paths, manifest, auto-verify).
- [ ] **Tobii device plugin**: start/stop the on-device SD recording via
      the G3 HTTP API (g3pylib) and gate on calibration — see the
      backlog in docs/architecture.md ("two machine actions + one human
      step").
- [ ] Post-stop offload hooks (ZedBox rsync, Tobii HTTP download) once
      those scripts exist.
