# Communication hardware

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-06-01

## Options at a glance

| Setup                                   | Quality                       | Cost  | Wear burden | Sim-room fit          |
|-----------------------------------------|-------------------------------|-------|-------------|-----------------------|
| Single room mic (omni or cardioid)      | Baseline, ~22-24% DER expected | $     | None        | Simplest              |
| USB mic array (ReSpeaker XVF-3000 or XVF-3800) | Improved via beamforming + AEC | $$    | None        | **Recommended entry** |
| Per-speaker lavaliers (wired or wireless) | Best; DER < 10% possible      | $$$   | Setup + subject compliance | Best data, most operational burden |

**Recommended progression:** start with a mic array, characterize what you
get, upgrade to lavaliers if the array's DER isn't good enough for the
analyses you need.

## USB mic arrays

Two ReSpeaker generations and one alternative are worth knowing.

### ReSpeaker Mic Array v2.0 — XMOS XVF-3000

- 4 mics, circular array
- USB audio (UAC 1.0)
- Onboard DSP: beamforming, AEC, dereverberation, noise suppression, VAD, direction-of-arrival (DoA)
- ~$70-90
- The "classic" — well-documented, widely deployed in voice-UI work
- **DoA output is directly useful as a speaker-counting prior** for diarization

### ReSpeaker (v3, mic array variants) — XMOS XVF-3800

Same VocalFusion family, newer chip generation. XMOS's product positioning
distinguishes them but Seeed's product-page comparisons are famously
unclear. The practical differences:

- **Mic count:** XVF-3800 supports more mics (typically 6-8 vs. 4 on XVF-3000). Higher spatial resolution.
- **Multi-beam output** — the important one: XVF-3800 can output *multiple simultaneous beams*, giving you 2-4 spatially-separated audio channels routed to different speakers' estimated directions. These feed into diarization as pseudo-per-speaker channels — a meaningful upgrade over a single mono beam. XVF-3000 is single-beam.
- **Conferencing-optimized DSP:** better AEC in speaker + mic feedback loops. Matters if the sim scenario has announcement audio or a vocal mannequin; less otherwise.
- **USB Audio Class 2.0** — higher sample rates, multi-channel out via UAC.
- **Firmware / tooling:** newer XMOS SDK support, longer active development horizon.
- **Cost:** modestly higher; still well under $500.

**Bottom line for sim center:** the multi-beam output is the meaningful
advantage. If you're building the pipeline to feed diarization with multiple
spatial channels, XVF-3800 gives you that natively. If you'll use only a
single beam or the raw mic signals, XVF-3000 is fine.

> [!WARNING]
> Seeed's product-page docs don't always match XMOS's chip datasheets. Before
> committing to XVF-3800, verify that the specific ReSpeaker SKU's shipping
> firmware and Python driver actually expose multi-channel-out mode. XMOS's
> VocalFusion documentation is more authoritative than Seeed's for feature
> verification.

<!-- TODO(unassigned): Confirm exact XVF-3800 ReSpeaker product SKU targeted, multi-beam output support in current firmware, and USB channel layout. Consult XMOS VocalFusion docs directly. -->

### Alternative: MiniDSP UMA-8 v2

- 7 MEMS mics in a circular array
- Onboard beamforming, AEC, noise suppression
- Similar price bracket
- Less directly integrated with popular Python voice stacks — more integration work

### What the deep-research pass verified vs. what it didn't

**Verified (2026-06-01):** XMOS XVF-3000 hardware capabilities per Seeed / XMOS datasheets.

**Not verified:** No published 2025-2026 benchmark quantifies how much
**DER or WER** a sub-$500 array actually improves vs. a single room mic in
a noisy multi-speaker room. The improvement is architecturally motivated
(beamforming, AEC, spatial info) but should be **empirically validated
with a pilot** before procurement commitments.

## Mounting and placement

<!-- TODO(unassigned): Room-position recommendations for arrays — typically ceiling-mounted or on the debrief-table center. Coverage vs. subject-motion tradeoffs. Note that DoA quality degrades with reverb and near-array reflections; distance from walls matters. -->

## Per-speaker lavaliers (upgrade path)

<!-- TODO(unassigned): If pilot DER on the array falls short of what your analyses need, document the lavalier upgrade: wireless UHF vs. 2.4 GHz systems, mixer/interface options, subject-consent flow, in-session fitting protocol, per-channel LSL outlets. -->

## LSL integration

The room mic (or array output) publishes timestamps as an LSL marker
stream; raw audio is written separately to WAV. Multi-beam arrays would
publish per-channel marker streams. See:

- [`shared/lsl_bridges/`](../../shared/lsl_bridges/README.md) — planned `room_mic_marker.py`
- [`docs/time-sync.md`](../../docs/time-sync.md) — Layer 2 architecture
