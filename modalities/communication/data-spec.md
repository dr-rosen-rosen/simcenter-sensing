# Communication data spec

> **Status:** stub
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## Raw

Session audio — WAV file(s):

| Config                             | Channels | Sample rate            | Notes                              |
|------------------------------------|----------|------------------------|------------------------------------|
| Single mic                         | 1        | 16 kHz min, 48 kHz preferred | Simplest                     |
| ReSpeaker array (single beam)      | 1        | 48 kHz                 | Beamformed by array DSP            |
| ReSpeaker XVF-3800 (multi-beam)    | 4-6      | 48 kHz                 | Spatially-separated pseudo-channels |
| Lavalier per speaker               | N        | 48 kHz                 | Best; separate WAV per speaker     |

Audio files are **re-identifiable (voice is biometric)** and treated as
raw subject-data tier per
[`docs/data-governance.md`](../../docs/data-governance.md).

Direction-of-arrival (DoA), if the array publishes it, is a separate
low-rate timeseries alongside audio — useful as a speaker-counting prior
downstream (see [processing.md](processing.md)).

## Interim

Diarized turn table (long-form CSV):

| Field                   | Type   | Notes |
|-------------------------|--------|-------|
| `t_start_canonical`     | float  | seconds since session start (canonical clock) |
| `t_end_canonical`       | float  |       |
| `speaker`               | string | `S1`, `S2`, ... (session-local) or role name if enrolled |
| `text`                  | string | ASR transcript for this turn |
| `word_start`, `word_end`| list   | word-level timestamps from WhisperX alignment |
| `confidence`            | float  | joint ASR + diarization confidence |
| `overlap`               | bool   | overlap detected during this turn |
| `source`                | string | provenance — `pyannote-3.1`, `whisperx-large-v3-int8`, etc. |

## Derived

Turn-level flow measures — computed per session, per speaker, or per team.

<!-- TODO(unassigned): Define exact fields once shared/flow_analysis/ is built. Candidate measures: per-speaker total speaking time, mean turn duration, turn-taking rate, overlap rate, pause distribution (gaps between turns), response latency by speaker-pair, interruption count, cumulative speaking-time Gini across the team. -->

## Naming

Per [`docs/identifiers.md`](../../docs/identifiers.md):

```
<study>_<subject-or-team>_<session>[_<run>]_audio.wav      # raw single/beamformed
<study>_<subject-or-team>_<session>[_<run>]_audio-ch<N>.wav # raw multi-channel (per beam)
<study>_<subject-or-team>_<session>[_<run>]_doa.csv        # DoA timeseries (if published)
<study>_<subject-or-team>_<session>[_<run>]_turns.csv      # interim diarized transcript
<study>_<subject-or-team>_<session>[_<run>]_flow.csv       # derived flow measures
```
