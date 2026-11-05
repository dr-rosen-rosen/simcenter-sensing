#!/usr/bin/env python3
"""Synthetic camera: POSTs generated JPEG frames to the console adapter.

Stands in for the ZedBox preview push so the imagery path can be developed
and demoed with no hardware. Each frame shows the source name, a counter,
a wall-clock timestamp, and a moving block (so motion is obvious).

Usage:
    python simulate_frames.py [--source sim-cam01] [--rate 1.0]
                              [--host localhost] [--port 8300]
"""
import argparse
import datetime as dt
import io
import sys
import time
import urllib.request

from PIL import Image, ImageDraw


def make_frame(source, n, w=640, h=360):
    img = Image.new("RGB", (w, h), (18, 26, 34))
    d = ImageDraw.Draw(img)
    # moving block
    x = (n * 23) % (w - 60)
    y = 60 + (n * 11) % (h - 140)
    d.rectangle([x, y, x + 60, y + 60], fill=(80, 160, 220))
    # labels
    d.text((12, 10), f"{source}", fill=(230, 230, 230))
    d.text((12, 28), dt.datetime.now().strftime("%H:%M:%S"), fill=(180, 220, 180))
    d.text((12, h - 24), f"frame {n}", fill=(160, 160, 160))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", default="sim-cam01")
    ap.add_argument("--rate", type=float, default=1.0, help="frames per second")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=8300)
    args = ap.parse_args()

    url = f"http://{args.host}:{args.port}/api/frame?source={args.source}"
    print(f"Posting {args.rate}/s to {url} - Ctrl+C to stop")
    n = 0
    try:
        while True:
            body = make_frame(args.source, n)
            try:
                req = urllib.request.Request(url, data=body, method="POST")
                urllib.request.urlopen(req, timeout=2.0)
            except Exception as e:
                print(f"post failed ({e}); is the adapter running?", file=sys.stderr)
            n += 1
            time.sleep(1.0 / args.rate)
    except KeyboardInterrupt:
        print(f"\nStopped after {n} frames")
    return 0


if __name__ == "__main__":
    sys.exit(main())
