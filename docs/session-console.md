# Session console (Open MCT) — evaluation and plan

> **Status:** MVP implemented (2026-10-23) — see [`tools/session_console/`](../tools/session_console/README.md);
> evaluation below retained for rationale. Lab smoke test pending.
> **Owner:** unassigned
> **Last reviewed:** 2026-10-23

A live control panel + post-session review console for data-collection
sessions, built on [NASA Open MCT](https://nasa.github.io/openmct/)
(Apache-2.0, actively developed). Evaluated 2026-10-13; verdict:
**feasible and a good conceptual fit**, with one weak spot (continuous
video) and one real build cost (a custom LSL adapter). Planned as a
post-capture-validation layer — see [Constraints](#constraints) before
anything else.

## Why Open MCT fits this system

- **LSL streams are telemetry** in Open MCT's native sense — timestamped
  numeric channels. The match is structural, not metaphorical.
- **LSL is multi-consumer by design**: the console subscribes to the same
  streams LabRecorder records, as a parallel reader. It can crash, lag,
  or be absent without endangering capture.
- **One adapter, not N device integrations** — everything already arrives
  through LSL (EmotiBit native, Tobii via G3LSLConnector, ZED frame
  markers, mic markers; see [time-sync.md](time-sync.md)).

What the framework provides out of the box:

| Capability        | Use here                                                        |
|-------------------|-----------------------------------------------------------------|
| Display layouts   | Drag-and-drop session panels (per-subject physio strips, stream-alive indicators, battery gauges) — built in the UI, no code |
| Time conductor    | One global scrub/zoom across every panel; realtime ↔ historical switching. The killer feature: post-session review of an aligned multimodal session |
| Notebook          | Timestamped operator annotations during the session — the run sheet, digitized, on the same timeline as the data |
| Condition sets    | "EmotiBit battery < 20%", "no samples from stream X for 10 s" → visual alarms, by configuration |
| Imagery view      | Timestamped stills on a scrubable timeline (see video limitation below) |

## Architecture sketch

```
LSL streams (lab LAN)
   │  (parallel subscription — LabRecorder remains the recorder of record)
   ▼
LSL adapter service (Python/pylsl or Node; runs on analysis laptop)
   ├─ WebSocket endpoint        → Open MCT realtime telemetry
   ├─ HTTP endpoint over an     → Open MCT historical telemetry
   │  in-memory ring buffer       (session-scoped; NOT an archive)
   └─ Auto-generates the Open MCT object tree from LSL stream metadata
      (names, channel counts, rates)
   ▼
Open MCT (static web app behind nginx/simple server, on analysis laptop)
   └─ viewed from any browser on the lab LAN
```

Reference implementations of exactly this shape:
[openmct-quickstart and openmct-yamcs](https://github.com/nasa/openmct)
(linked from the main repo). Estimated effort for a working MVP:
**3-5 days** for someone comfortable in Python with modest JS. No
published LSL → Open MCT bridge exists (verified 2026-10-13), so this is
a build, not an install — but it is the framework's designed-for
extension pattern, and a well-bounded student project.

Proposed code home when built: `tools/session-console/` (it is a
consumer of LSL, not a bridge into it, so it does not belong under
`shared/lsl_bridges/`).

## Known limitation: continuous video

Open MCT's imagery model is timestamped stills (spacecraft-camera
heritage), not live video. For a session console this is mostly fine —
the operator needs "cameras alive and framed," not smooth video. Two
workarounds:

1. **Preview frames (recommended):** 1-2 Hz JPEGs from the ZED (and/or
   Tobii scene camera) published as imagery telemetry. These land on the
   scrubable timeline, which is genuinely useful post-hoc.
2. **Embedded live stream:** MJPEG/WebRTC in a custom view or Web Page
   object. Live, but outside the time-conductor model.

Full-rate synchronized video review stays in the offline pipeline; the
console is not for that.

## Alternative considered: Grafana

Grafana stands up a basic live dashboard faster (days → hours) and is
the well-trodden choice for "numbers on panels with alerts." It lacks
the time conductor, imagery timeline, notebook, and session-ops model —
it is a monitoring dashboard, not a session console. Given the long game
(scrubbing aligned multimodal sessions; annotating during collection),
Open MCT's setup cost buys things Grafana structurally cannot. Fully
custom (FastAPI + React) was ruled out: most work, least leverage.

Revisit Grafana only if the Open MCT adapter stalls and a quick
monitoring-only dashboard is needed as a stopgap.

## Constraints

1. **Never on the capture-critical path.** Sessions must be fully
   collectable with the console absent or broken. LabRecorder + Layer 1
   sync markers ([time-sync.md](time-sync.md)) remain the system of
   record.
2. **Build only after capture is validated** — the router-LAN validation
   sequence in [architecture.md](architecture.md) comes first.
3. **The ring buffer is not storage.** Session archiving stays per
   [storage.md](storage.md); the console displays, it does not retain.

## Phased plan

1. **MVP:** Open MCT with localStorage persistence + LSL adapter serving
   EmotiBit channels + stream-alive staleness indicators + one display
   layout + notebook enabled.
2. **Alarms:** condition sets for battery and stream dropout.
3. **Imagery:** ZED / Tobii preview frames at 1-2 Hz.
4. **Historical mode:** HTTP endpoint over the ring buffer; evaluate
   CouchDB persistence if layouts need to be shared across machines.

## TODOs

<!-- TODO(unassigned): After capture validation, prototype the LSL adapter — start from the openmct-quickstart pattern; auto-populate the object tree from LSL stream metadata -->
<!-- TODO(unassigned): Decide MVP hosting (nginx vs. simple static server) on the analysis laptop -->
<!-- TODO(unassigned): Pilot preview-frame imagery from the ZED (frame grab → JPEG → imagery telemetry) -->
<!-- TODO(unassigned): Re-check for a community LSL→Open MCT bridge before building (verified absent 2026-10-13) -->
