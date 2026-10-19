#!/usr/bin/env python3
"""Keyboard marker outlet: timestamped operator annotations into LSL.

Press Enter to publish a marker; type a label first (e.g. "clap",
"scenario start") to annotate it. Run this alongside the Layer-1 physical
sync marker (clap + flash) so the run sheet and the .xdf agree on event
times: the operator claps, then immediately hits Enter with label "clap".

LSL stream schema:
    name:           simcenter.test.keyboard (override with --name)
    type:           Markers
    channel_count:  1 (string)
    nominal_srate:  0 (irregular)
    sample format:  the typed label, or "mark" if empty
"""
import argparse
import socket
import sys

from pylsl import StreamInfo, StreamOutlet, local_clock


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--name", default="simcenter.test.keyboard")
    args = ap.parse_args()

    info = StreamInfo(args.name, "Markers", 1, 0, "string",
                      f"kbd-{socket.gethostname()}")
    outlet = StreamOutlet(info)
    print(f"Publishing {args.name}. Type a label and press Enter "
          f"(empty = 'mark'); Ctrl+C or Ctrl+D to stop")
    try:
        while True:
            label = input("> ").strip() or "mark"
            ts = local_clock()
            outlet.push_sample([label], ts)
            print(f"  {label} @ LSL {ts:.3f}")
    except (KeyboardInterrupt, EOFError):
        print("\nStopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
