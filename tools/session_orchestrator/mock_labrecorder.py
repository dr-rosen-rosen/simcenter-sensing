#!/usr/bin/env python3
"""Mock LabRecorder remote-control server for orchestrator testing.

Listens on the RCS port (default 22345), accepts connections, and logs
every command received. Does NOT record anything - it exists purely to
test the orchestrator's protocol exchange without LabRecorder installed.

Usage:
    python mock_labrecorder.py [--port 22345]
"""
import argparse
import socket
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=22345)
    args = ap.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", args.port))
    srv.listen(1)
    print(f"Mock LabRecorder RCS listening on 127.0.0.1:{args.port} - Ctrl+C to stop")
    try:
        while True:
            conn, addr = srv.accept()
            print(f"[conn] {addr}", flush=True)
            buf = b""
            while True:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    print(f"[cmd ] {line.decode(errors='replace')}", flush=True)
            print("[disc]")
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
