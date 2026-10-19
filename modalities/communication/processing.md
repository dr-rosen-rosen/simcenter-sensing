# Communication processing

> **Status:** drafted (planning)
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

Planning-stage document capturing the intended Phase-4 pipeline. Backed
by a deep-research pass (2026-06-01) verifying licensing, benchmarks,
and rejected candidates. **Re-scan Q4 2026 before code lock-in** — the
streaming diarization space is moving fast.

## Pipeline

```
audio (WAV — 16 kHz mono OR multi-channel array output)
  ↓ VAD + segmentation
diarized turns (speaker labels + start/end timestamps)
  ↓ ASR per turn
diarized transcript (speaker, start, end, text, confidence)
  ↓ flow analysis
turn-level measures (speaking time, overlap, pauses, response latency, ...)
```

## Chosen components

All open-source and license-compatible with the MIT repo.

| Stage             | Component                                          | License     |
|-------------------|----------------------------------------------------|-------------|
| Diarization       | `pyannote/speaker-diarization-3.1`                 | MIT         |
| Joint diar + sep  | `pyannote/separation-ami-1.0` (trained on AMI-SDM) | MIT         |
| Streaming wrapper | Diart                                              | Apache-2.0  |
| ASR               | faster-whisper large-v3 (INT8)                     | MIT         |
| Composed pipeline | WhisperX (Whisper + pyannote)                      | BSD-2       |
| Flow analysis     | Custom (built in-repo)                             | MIT         |

## Why this stack

- **pyannote.audio 3.x is the strongest MIT-licensed backbone** for the
  target acoustic condition. `speaker-diarization-3.1` reports **18.8% DER
  on AMI headset** (near-field), 21.7% on DIHARD-3 Full, 11.3% on
  VoxConverse v0.3.
- **`separation-ami-1.0`** performs joint diarization + speech separation
  on 5-second 16 kHz mono chunks and was trained specifically on **AMI
  single-distant-microphone** — the exact acoustic condition of a single
  room mic. Capped at 3 concurrent output speakers (see open questions).
- **Diart** (JOSS 2024, peer-reviewed) implements chunked / streaming
  diarization on top of pyannote pipelines, meeting the 5-30 s chunked
  latency requirement without a rewrite.
- **faster-whisper large-v3 INT8** — ~35× RTF on L40S, ~3 GB VRAM; runs
  comfortably on RTX 3060+ and Apple Silicon. WhisperX composes it with
  pyannote for word-timestamped diarized transcripts.

## Rejected candidates (documented so future contributors don't rediscover them)

### NVIDIA Streaming Sortformer v2 — architectural speaker cap

Attractive latency profile (10 s buffer at RTF 0.005, 30 s at RTF 0.002)
and constant-memory sliding window — a great fit for the 5-30 s chunked
regime **on paper**. But there is a **hard 4-speaker architectural cap**:
DER jumps from **13.24 %** (1-4 speakers) to **42.56 %** (5-9 speakers) on
DIHARD-III Eval. Since sim teams routinely exceed 4 speakers, this rules
Sortformer out as primary. Stays interesting as a fast small-team
benchmark reference.

### Reverb (Rev.com) — licensing dealbreaker

Integrated WeNet ASR + pyannote-based diarization; would be attractive
technically. But the **model weights ship under Rev's Non-Production
License** — explicitly excludes "live, real-world conditions, commercial
operations, revenue-generating activities, or direct interactions with
end users" and hosted/SaaS use. Code is Apache-2.0; **models cannot be
shipped in a public MIT methods repo**. Reference for internal benchmarks
only; never as a dependency.

## Realistic quality expectations

**Do not quote 18.8 % DER for single-room-mic sim recordings.** That
number is on AMI *headset* (near-field). The single-distant-microphone
(SDM) number for pyannote 3.1 is closer to **22-24 %** based on EEND-TA
baselines (Broughton et al., Interspeech 2025).

State-of-the-art distant-mic DER sits at **~14-15 %** (EEND-TA + scaled
pre-training, arXiv:2509.14737, 2025). So **~15 % DER is the floor even
with SOTA models; ~22-24 % is a realistic target** for the pyannote 3.x
pipeline in the sim-room acoustic condition.

Practical implications:

- **Aggregate flow measures** (per-speaker speaking time, turn-taking
  rate, overlap rate) are robust to DER at this level. Directionally
  trustworthy.
- **Turn-by-turn attribution** (who interrupted whom) is noisy at 22-24 %
  DER. Needs error bars or manual spot-checking for specific analyses.
- **Cross-session speaker identity** requires enrollment (each participant
  records a 30 s sample) — otherwise treat each session's speakers as
  `S1/S2/...` unlabeled.

## CHiME-7 / 8 DASR review — three caveats that shape the design

Cornell et al., July 2025 ([arXiv:2507.18161](https://arxiv.org/abs/2507.18161))
— the definitive multi-party distant-mic ASR review — documents:

1. **All top ensemble systems still rely on Guided Source Separation (GSS)**
   rather than end-to-end neural separation. Plan for a GSS-like re-separation
   stage before ASR if quality falls short at the pilot stage.
2. **First-pass speaker counting is the critical prerequisite** —
   downstream WER compounds errors from this stage. Validate speaker
   counting explicitly (e.g., use ReSpeaker DoA as a prior; sanity-check
   against manual counts on pilot recordings).
3. Transcribing spontaneous multi-speaker speech in noisy/reverberant
   environments **"remains difficult even when using computationally
   intensive system ensembles."** Do not expect solved-problem quality
   regardless of stack choice.

## Hardware requirements

| Hardware               | Full stack feasibility                                              |
|------------------------|---------------------------------------------------------------------|
| RTX 4090 / A100 / L40S | Comfortable; realtime with headroom                                 |
| RTX 3060 12 GB         | Minimum for a single live stream (faster-whisper large-v3 INT8)     |
| Apple Silicon (M2+)    | Viable; whisper.cpp Metal, ~1× to ~2.6× realtime for large-v3       |
| CPU only               | Batch post-hoc only; not benchmarked in surviving evidence          |

VRAM notes:

- faster-whisper large-v3 INT8: ~3 GB VRAM
- WhisperX composition adds 1-2 GB VRAM for the pyannote pass

## Open questions (from research)

1. **Sub-$500 mic array DER lift** — no verified benchmark vs. a single
   mic in a noisy multi-speaker room. Pilot before committing procurement
   (see [hardware.md](hardware.md)).
2. **`separation-ami-1.0`'s 3-speaker cap on 5-8-speaker teams** — can it
   be composed with a first-pass counter (pyannote 3.1) so it runs
   per-window on the 3 most active speakers?
3. **No canonical open-source flow-analysis library** surfaced — build
   in-repo under `shared/`.
4. Is there an open **GSS-style re-separation stage** compatible with a
   pyannote frontend for the on-prem sim-room case?

## TODOs

<!-- TODO(unassigned): Prototype pyannote 3.1 + Diart + faster-whisper against a pilot recording; measure DER on a manually-diarized short segment; report numbers back into this doc -->
<!-- TODO(unassigned): Decide separation-ami-1.0 usage — skip (single-beam) or wrap in a per-window "top-3-active-speakers" composer to accommodate 5+ speakers -->
<!-- TODO(unassigned): Build in-repo turn-taking / flow analysis (shared/flow_analysis/) — no canonical open library exists per 2026-06-01 research -->
<!-- TODO(unassigned): Q4 2026 landscape re-scan before code lock-in — Sortformer descendants, EEND-TA successors, any new integrated pipelines, updated benchmarks -->
<!-- TODO(unassigned): Read TeamVision (arXiv:2501.09930) and extract transferable design choices for the sim-center debrief dashboard use case -->
