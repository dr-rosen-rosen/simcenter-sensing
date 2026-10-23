# Session console (Open MCT)

> **Status:** MVP built + tested against synthetic streams (2026-10-23);
> lab smoke test pending
> **Owner:** unassigned

Live session console per the evaluation in
[docs/session-console.md](../../docs/session-console.md): every LSL
stream on the network, browsable and plottable in NASA Open MCT with a
realtime time conductor, served entirely from the analysis laptop.

**Strictly read-only / parallel:** the adapter is just another LSL
consumer. It can crash or be absent without affecting LabRecorder or any
capture path.

## Pieces

| File | Purpose |
|---|---|
| `adapter.py` | LSL → Open MCT bridge: auto-discovers streams, ring-buffers 10 min of samples, serves history (HTTP) + realtime (WebSocket) + the web app itself on one port |
| `web/index.html` | Open MCT app shell (LocalStorage persistence, UTC time system, realtime/fixed conductor) |
| `web/lsl-plugin.js` | Teaches Open MCT about LSL: object tree from `/api/streams`, history requests, WebSocket subscriptions |
| `get_openmct.py` | One-time fetch of the Open MCT dist into `web/openmct/` (gitignored) |

## Setup (once per machine)

```
uv sync                                   # websockets joined the deps
uv run python tools/session_console/get_openmct.py
```

Open MCT must be served same-origin (SharedWorkers refuse cross-origin,
and the lab LAN has no internet), hence the local fetch — needs internet
once, like installing LabRecorder.

## Run

```
uv run python tools/session_console/adapter.py
```

Then open http://localhost:8300 (or http://<analysis-laptop>:8300 from
any machine on the lab LAN). Streams appear under **LSL Streams** as
they're discovered; click to plot; build display layouts with Create →
Display Layout (persisted in the browser's localStorage).

Timestamps are converted from LSL clock to Unix epoch ms in the adapter,
so the UTC time conductor and realtime mode work natively.

## Current scope and known limits

- **Numeric streams**: plots, including multi-channel (ch0..chN keys).
  **Marker streams**: exposed with a `text` value — view as table.
- Ring buffer is 10 min (`--ring-seconds`); the console is for live
  monitoring and short lookback, not archival review. The `.xdf` remains
  the record.
- Duplicate stream names: first-seen wins in the adapter registry — the
  orchestrator's preflight is the guard against duplicates, not the console.
- LocalStorage layouts are per-browser; fine for a single operator
  station. CouchDB only if layouts must be shared.

## Next steps

- [ ] Lab smoke test against real streams (EmotiBit + mic + ZED + Tobii)
- [ ] Build the standard session display layout (per-subject physio strip,
      stream-health row) and document it
- [ ] Condition sets for battery/dropout alarms (Open MCT UI config)
- [ ] ZED/Tobii preview frames as imagery (per session-console.md phase 3)
- [ ] Consider surfacing orchestrator manifest events as an annotation
      stream in the console
