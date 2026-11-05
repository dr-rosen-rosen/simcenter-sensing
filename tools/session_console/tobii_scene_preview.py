#!/usr/bin/env python3
"""Tobii Glasses 3 scene-camera preview -> session console imagery.

Runs on the Tobii host laptop (dual-homed: WiFi to the unit's AP, LAN to
the console). Pulls the unit's live RTSP scene stream, downscales ~1 Hz
frames to JPEG, and POSTs them to the console adapter's /api/frame
endpoint - the same sidecar path the ZedBox uses. Nothing touches LSL,
the .xdf, or the on-device recording.

The Glasses 3 recording unit serves scene video at
    rtsp://<unit-ip>:8554/live/all
(<unit-ip> = the WiFi adapter's default gateway when joined to the
unit's TG03B-* AP; see ipconfig). If your firmware serves a different
path, pass the full URL with --rtsp.

Note: this is the RAW scene camera - no gaze overlay. A gaze-overlaid
preview (decode the gaze stream, draw the dot before posting) is a
possible later upgrade.

Usage:
    python tobii_scene_preview.py --unit 192.168.75.51
    python tobii_scene_preview.py --rtsp <full-url-or-file> [--rate 1.0]
"""
import argparse
import sys
import time
import urllib.request

import cv2


def open_capture(src):
    cap = cv2.VideoCapture(src, cv2.CAP_FFMPEG)
    return cap if cap.isOpened() else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--unit", help="Glasses 3 recording-unit IP (the WiFi gateway on its AP)")
    ap.add_argument("--rtsp", help="full RTSP URL (or any cv2-openable source; overrides --unit)")
    ap.add_argument("--rate", type=float, default=1.0, help="preview frames per second")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--console", default="localhost", help="console adapter host")
    ap.add_argument("--port", type=int, default=8300)
    ap.add_argument("--source", default="tobii-scene", help="frame source name in the console")
    args = ap.parse_args()

    if not args.rtsp and not args.unit:
        sys.exit("Give --unit <ip> (or a full --rtsp URL). The unit's IP is the "
                 "WiFi adapter's default gateway while joined to its TG03B-* AP.")
    src = args.rtsp or f"rtsp://{args.unit}:8554/live/all"
    post_url = f"http://{args.console}:{args.port}/api/frame?source={args.source}"
    min_gap = 1.0 / args.rate

    print(f"Scene source: {src}")
    print(f"Posting ~{args.rate}/s to {post_url} - Ctrl+C to stop")

    cap = None
    last_post = 0.0
    posted = 0
    try:
        while True:
            if cap is None:
                cap = open_capture(src)
                if cap is None:
                    print("Cannot open stream (unit on? laptop on its TG03B-* WiFi? "
                          "IP right?) - retrying in 3s", file=sys.stderr)
                    time.sleep(3.0)
                    continue
                print("Stream open")
            ok, frame = cap.read()   # read every frame so the buffer never lags
            if not ok:
                print("Stream ended/failed - reconnecting in 2s", file=sys.stderr)
                cap.release()
                cap = None
                time.sleep(2.0)
                continue
            now = time.monotonic()
            if now - last_post < min_gap:
                continue
            last_post = now
            h, w = frame.shape[:2]
            if w > args.width:
                frame = cv2.resize(frame, (args.width, int(h * args.width / w)))
            enc, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not enc:
                continue
            try:
                req = urllib.request.Request(post_url, data=buf.tobytes(), method="POST")
                urllib.request.urlopen(req, timeout=2.0)
                posted += 1
            except Exception as e:
                print(f"post failed ({e}) - console adapter running?", file=sys.stderr)
    except KeyboardInterrupt:
        print(f"\nStopped after {posted} frames")
    finally:
        if cap is not None:
            cap.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
