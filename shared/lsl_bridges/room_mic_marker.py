#!/usr/bin/env python3
"""Room-microphone capture: WAV to disk + LSL marker stream.

Captures audio from a USB microphone / mic array (e.g., ReSpeaker with
XVF-3800) to a WAV file, and publishes an LSL marker stream that maps WAV
sample positions to LSL time, so the recording can be aligned with other
modalities post hoc.

LSL stream schema:
    name:           simcenter.mic.marker (override with --stream-name)
    type:           Markers
    channel_count:  1 (string)
    nominal_srate:  0 (irregular)
    sample format:  "frames=<total_frames_written> sr=<samplerate>"
    timestamp:      pylsl local_clock() captured in the audio callback for
                    the block that crossed the marker boundary

Alignment: a marker's WAV time is frames/sr; its LSL time is the stream
timestamp. Fit a line through the (wav_time, lsl_time) pairs to map the
whole file onto LSL time. The WAV keeps writing even if LSL has no
consumers or fails; Ctrl+C stops cleanly.

Usage:
    python room_mic_marker.py --list-devices
    python room_mic_marker.py --device XVF --out session01_audio.wav
    python room_mic_marker.py --dry-run
"""
import argparse
import datetime as dt
import queue
import sys
import wave

import sounddevice as sd
from pylsl import StreamInfo, StreamOutlet, local_clock


def pick_device(spec):
    if spec is None:
        return None  # sounddevice default input
    try:
        return int(spec)
    except ValueError:
        pass
    matches = [
        i for i, d in enumerate(sd.query_devices())
        if spec.lower() in d["name"].lower() and d["max_input_channels"] > 0
    ]
    if not matches:
        sys.exit(f"No input device matching {spec!r}; try --list-devices")
    if len(matches) > 1:
        names = ", ".join(f"{i}: {sd.query_devices(i)['name']}" for i in matches)
        sys.exit(f"Ambiguous device {spec!r} ({names}); use the index instead")
    return matches[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", help="input device index or name substring (default: system default)")
    ap.add_argument("--list-devices", action="store_true", help="list audio devices and exit")
    ap.add_argument("--samplerate", type=int, default=48000)
    ap.add_argument("--channels", type=int, help="channels to record (default: all the device offers)")
    ap.add_argument("--out", help="output WAV path (default: mic_YYYYMMDD-HHMMSS.wav)")
    ap.add_argument("--marker-interval", type=float, default=1.0, help="seconds of audio per LSL marker")
    ap.add_argument("--stream-name", default="simcenter.mic.marker")
    ap.add_argument("--dry-run", action="store_true", help="print device + outlet metadata and exit")
    args = ap.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return 0

    device = pick_device(args.device)
    dev_info = sd.query_devices(device, "input")
    channels = args.channels or dev_info["max_input_channels"]
    out_path = args.out or dt.datetime.now().strftime("mic_%Y%m%d-%H%M%S.wav")

    print(f"Device:     {dev_info['name']}")
    print(f"Channels:   {channels}   Samplerate: {args.samplerate}")
    print(f"WAV out:    {out_path}")
    print(f"LSL stream: {args.stream_name} (Markers, every {args.marker_interval}s of audio)")
    if args.dry_run:
        return 0

    info = StreamInfo(args.stream_name, "Markers", 1, 0, "string",
                      f"mic-{dev_info['name'][:32]}")
    outlet = StreamOutlet(info)

    blocks = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        blocks.put((indata.copy(), local_clock()))

    marker_every_frames = int(args.marker_interval * args.samplerate)
    total_frames = 0
    next_marker_at = marker_every_frames

    wav = wave.open(out_path, "wb")
    wav.setnchannels(channels)
    wav.setsampwidth(2)  # int16
    wav.setframerate(args.samplerate)

    stream = sd.InputStream(device=device, channels=channels,
                            samplerate=args.samplerate, dtype="int16",
                            callback=callback)
    print("Recording - Ctrl+C to stop")
    try:
        with stream:
            while True:
                data, lsl_ts = blocks.get()
                wav.writeframes(data.tobytes())
                total_frames += len(data)
                if total_frames >= next_marker_at:
                    try:
                        outlet.push_sample(
                            [f"frames={total_frames} sr={args.samplerate}"], lsl_ts)
                    except Exception as e:  # LSL must never kill capture
                        print(f"LSL push failed: {e}", file=sys.stderr)
                    next_marker_at += marker_every_frames
    except KeyboardInterrupt:
        pass
    finally:
        wav.close()
        print(f"\nStopped. {total_frames / args.samplerate:.1f}s "
              f"({total_frames} frames) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
