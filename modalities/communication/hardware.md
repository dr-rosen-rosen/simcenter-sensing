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

### Lab unit: ReSpeaker XVF3800 with XIAO ESP32S3 (as deployed)

> **Device state (2026-10-19):** the lab's unit is the **XIAO ESP32S3
> variant**, flashed to **USB firmware v2.1.1 `16k6ch`**. It enumerates as
> "reSpeaker XVF3800 4-Mic Array" — **6 input channels @ 16 kHz**:
> channels 1-2 = processed stereo (voice-enhanced), channels 3-6 = the
> four **raw** microphones (unprocessed; lower level by design — keep
> original levels for algorithm work).
>
> Gotchas learned the hard way:
>
> - The XIAO variant **ships with I2S firmware, which is invisible to
>   USB hosts**. If the device ever stops enumerating after a reflash,
>   that's why. USB firmware images live in
>   [Seeed's repo](https://github.com/respeaker/reSpeaker_XVF3800_USB_4MIC_ARRAY/tree/master/xmos_firmwares/usb).
> - **Flash procedure:** hold Mute while connecting power until the red
>   LED blinks (Safe Mode), then
>   `dfu-util -R -e -a 1 -D <firmware.bin>` ([Seeed FAQ](https://wiki.seeedstudio.com/respeaker_xvf3800_faq/)).
> - **Use the XMOS USB-C port** (near the 3.5 mm jack) with a data
>   cable. The other USB-C port belongs to the XIAO ESP32-S3 and will
>   never show audio.
> - Record at `--samplerate 16000` (the firmware's native rate).
> - Firmware v2.0.6+ exposes a **`DOA_VALUE`** USB command (live
>   direction-of-arrival 0-359° + speech-detected flag, via Seeed's
>   `xvf_host.py`) — a future speaker-direction prior for diarization
>   without touching the audio path.

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
