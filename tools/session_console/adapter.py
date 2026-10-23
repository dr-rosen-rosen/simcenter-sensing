#!/usr/bin/env python3
"""LSL -> Open MCT adapter: ring-buffered history + realtime WebSocket.

Discovers every LSL stream on the network, buffers recent samples in
memory (default 10 minutes), and serves them to the Open MCT session
console (web/) three ways:

    GET  /api/streams                      stream inventory (object tree)
    GET  /api/history?stream=N&start=&end= buffered samples, epoch ms
    WS   :<port+1>                         {"op":"subscribe","stream":N}
                                           -> {"stream":N,"points":[...]}

plus static file serving for web/ itself, so the whole console is
http://<host>:8300 with no CORS complications.

Timestamps: LSL local_clock() seconds are converted to Unix epoch
milliseconds using a startup-computed offset, so Open MCT's UTC time
conductor works naturally.

The adapter is a read-only LSL consumer: it can crash, lag, or be absent
without affecting LabRecorder or any capture path.

Usage:
    python adapter.py [--port 8300] [--ring-seconds 600]
"""
import argparse
import asyncio
import functools
import http.server
import json
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# macOS: point pylsl at the locally staged liblsl if not already set
if sys.platform == "darwin" and "PYLSL_LIB" not in os.environ:
    _local = os.path.expanduser("~/.local/lib/liblsl.dylib")
    if os.path.exists(_local):
        os.environ["PYLSL_LIB"] = _local

from pylsl import StreamInlet, local_clock, resolve_streams  # noqa: E402

import websockets  # noqa: E402

WEB_DIR = Path(__file__).resolve().parent / "web"

# LSL local_clock -> Unix epoch ms conversion, computed once
CLOCK_OFFSET_MS = time.time() * 1000.0 - local_clock() * 1000.0


class Stream:
    def __init__(self, info):
        self.name = info.name()
        self.type = info.type()
        self.channels = info.channel_count()
        self.nominal_hz = info.nominal_srate()
        self.fmt = "string" if info.channel_format() == 3 else "number"  # cf_string == 3
        self.ring = deque()          # (t_ms, values list)
        self.pending = []            # new samples since last broadcast
        self.lock = threading.Lock()
        self.alive = True

    def meta(self):
        return {"name": self.name, "type": self.type, "channels": self.channels,
                "nominal_hz": self.nominal_hz, "format": self.fmt}

    def append(self, t_ms, values, ring_ms):
        with self.lock:
            self.ring.append((t_ms, values))
            self.pending.append((t_ms, values))
            cutoff = t_ms - ring_ms
            while self.ring and self.ring[0][0] < cutoff:
                self.ring.popleft()

    def drain_pending(self):
        with self.lock:
            out, self.pending = self.pending, []
            return out

    def history(self, start_ms, end_ms, max_points=5000):
        with self.lock:
            pts = [(t, v) for t, v in self.ring if start_ms <= t <= end_ms]
        if len(pts) > max_points:
            stride = len(pts) // max_points + 1
            pts = pts[::stride]
        return pts


STREAMS = {}           # name -> Stream
STREAMS_LOCK = threading.Lock()


def reader(stream, inlet, ring_ms):
    try:
        while stream.alive:
            chunk, stamps = inlet.pull_chunk(timeout=0.5)
            for values, ts in zip(chunk, stamps):
                t_ms = ts * 1000.0 + CLOCK_OFFSET_MS
                stream.append(t_ms, list(values), ring_ms)
    except Exception as e:
        print(f"[reader] {stream.name} ended: {e}")
    finally:
        stream.alive = False
        try:
            inlet.close_stream()
        except Exception:
            pass


def discovery(ring_ms, interval=5.0):
    while True:
        try:
            found = resolve_streams(wait_time=1.0)
        except Exception as e:
            print(f"[discovery] resolve failed: {e}")
            time.sleep(interval)
            continue
        with STREAMS_LOCK:
            for info in found:
                name = info.name()
                if name in STREAMS and STREAMS[name].alive:
                    continue
                s = Stream(info)
                STREAMS[name] = s
                inlet = StreamInlet(info, max_buflen=30, recover=False)
                t = threading.Thread(target=reader, args=(s, inlet, ring_ms), daemon=True)
                t.start()
                print(f"[discovery] + {name} ({s.type}, {s.channels}ch @ {s.nominal_hz:g} Hz)")
        time.sleep(interval)


# ---------------------------------------------------------------------------
# HTTP: static web/ + JSON API
# ---------------------------------------------------------------------------

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/streams":
            with STREAMS_LOCK:
                return self._json([s.meta() for s in STREAMS.values()])
        if url.path == "/api/history":
            q = parse_qs(url.query)
            name = (q.get("stream") or [""])[0]
            start = float((q.get("start") or ["0"])[0])
            end = float((q.get("end") or [str(time.time() * 1000)])[0])
            with STREAMS_LOCK:
                s = STREAMS.get(name)
            if not s:
                return self._json({"error": f"unknown stream {name}"}, 404)
            pts = s.history(start, end)
            if s.fmt == "string":
                data = [{"t": t, "text": (v[0] if v else "")} for t, v in pts]
            else:
                data = [dict({"t": t}, **{f"ch{i}": x for i, x in enumerate(v)})
                        for t, v in pts]
            return self._json({"stream": name, "data": data})
        return super().do_GET()


# ---------------------------------------------------------------------------
# WebSocket: realtime subscriptions
# ---------------------------------------------------------------------------

SUBS = {}  # websocket -> set of stream names
SUBS_LOCK = threading.Lock()


async def ws_handler(websocket):
    with SUBS_LOCK:
        SUBS[websocket] = set()
    try:
        async for msg in websocket:
            try:
                m = json.loads(msg)
            except json.JSONDecodeError:
                continue
            if m.get("op") == "subscribe":
                with SUBS_LOCK:
                    SUBS[websocket].add(m.get("stream"))
            elif m.get("op") == "unsubscribe":
                with SUBS_LOCK:
                    SUBS[websocket].discard(m.get("stream"))
    finally:
        with SUBS_LOCK:
            SUBS.pop(websocket, None)


async def broadcaster():
    while True:
        await asyncio.sleep(0.2)
        with STREAMS_LOCK:
            streams = list(STREAMS.values())
        for s in streams:
            pts = s.drain_pending()
            if not pts:
                continue
            if s.fmt == "string":
                data = [{"t": t, "text": (v[0] if v else "")} for t, v in pts]
            else:
                data = [dict({"t": t}, **{f"ch{i}": x for i, x in enumerate(v)})
                        for t, v in pts]
            payload = json.dumps({"stream": s.name, "points": data})
            with SUBS_LOCK:
                targets = [ws for ws, names in SUBS.items() if s.name in names]
            for ws in targets:
                try:
                    await ws.send(payload)
                except websockets.exceptions.ConnectionClosed:
                    pass


async def ws_main(port):
    async with websockets.serve(ws_handler, "0.0.0.0", port):
        await broadcaster()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8300, help="HTTP port (WS uses port+1)")
    ap.add_argument("--ring-seconds", type=float, default=600.0)
    args = ap.parse_args()
    ring_ms = args.ring_seconds * 1000.0

    threading.Thread(target=discovery, args=(ring_ms,), daemon=True).start()

    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"Session console: http://localhost:{args.port}  (WS on {args.port + 1})")
    print(f"Ring buffer: {args.ring_seconds:.0f}s per stream. Ctrl+C to stop.")

    try:
        asyncio.run(ws_main(args.port + 1))
    except KeyboardInterrupt:
        print("\nStopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
