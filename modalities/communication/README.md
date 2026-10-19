# Communication analysis

> **Status:** drafted (planning) / not started (implementation)
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## Scope

Speaker diarization, transcription, and conversational-flow analysis from
audio captured during simulation sessions — primarily from a single room
microphone (with a documented upgrade path to small mic arrays and
per-speaker lavaliers).

## Phase

**Phase 4** in the repo plan. Nothing collected yet. This directory
captures the planning work (stack selection, hardware options, quality
expectations) that will inform Phase-4 kickoff. Backed by a deep-research
pass (2026-06-01) verifying licensing, benchmarks, and rejected candidates.

## Target regime

- **Latency:** chunked 5-30 s (post-scenario dashboards), not sub-second live
- **Team size:** 2-8 speakers
- **Language:** English (clinical speech)
- **Environment:** noisy, reverberant sim rooms with alarms/monitors, moving speakers
- **Compute:** on-prem (no cloud APIs — audio is voice-biometric)

## Planned stack

All MIT / Apache / BSD — compatible with the public MIT repo.

| Stage               | Component                                             | License    |
|---------------------|-------------------------------------------------------|------------|
| Diarization         | `pyannote/speaker-diarization-3.1`                    | MIT        |
| Joint diar + sep    | `pyannote/separation-ami-1.0` (trained on AMI-SDM)    | MIT        |
| Streaming wrapper   | Diart (JOSS 2024)                                     | Apache-2.0 |
| ASR                 | faster-whisper large-v3 (INT8)                        | MIT        |
| Composed pipeline   | WhisperX (Whisper + pyannote)                         | BSD-2      |
| Flow analysis       | Custom (built in-repo — no canonical open library)    | MIT        |

See [processing.md](processing.md) for full rationale, licensing verification,
rejected candidates, realistic quality expectations, and the CHiME-7/8 caveats
that shape the pipeline design.

## Section status

| Section          | File                                       | Status      |
|------------------|--------------------------------------------|-------------|
| Hardware         | [hardware.md](hardware.md)                 | drafted     |
| Pre-session      | [pre-session.md](pre-session.md)           | stub        |
| During-session   | [during-session.md](during-session.md)     | stub        |
| Troubleshooting  | [troubleshooting.md](troubleshooting.md)   | not started |
| Processing       | [processing.md](processing.md)             | drafted     |
| Data spec        | [data-spec.md](data-spec.md)               | stub        |

## Reference deployment

**TeamVision** (Yan et al., CHI 2025, [arXiv:2501.09930](https://arxiv.org/abs/2501.09930))
— in-the-wild nursing-simulation debrief dashboards from voice presence,
transcription, positioning, and body rotation. Closest published analog to
the intended Phase-4 deployment; recommended reading before kickoff.

## TODOs for collaborators

- [ ] Procure and pilot a mic array (ReSpeaker XVF-3000 v2.0 or XVF-3800 variant) — see [hardware.md](hardware.md)
- [ ] Prototype the pyannote + Diart + faster-whisper pipeline against pilot recordings
- [ ] Characterize actual DER + WER in the target acoustic environment (research surfaced benchmark ranges but no sim-specific numbers)
- [ ] Build in-repo turn-taking / flow-analysis helpers (no open library surfaced)
- [ ] Q4 2026 re-scan of the streaming diarization landscape before Phase-4 code lock-in — the space moves fast
- [ ] Read TeamVision paper; extract transferable design choices for the debrief dashboard
