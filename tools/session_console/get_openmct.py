#!/usr/bin/env python3
"""Fetch the Open MCT distribution into web/openmct/ (one-time, per machine).

The console must serve Open MCT same-origin: SharedWorkers refuse
cross-origin scripts, and the lab LAN has no internet anyway. This
downloads the npm tarball and extracts its dist/ next to index.html.
web/openmct/ is gitignored - run this once on each machine (requires
internet, like installing LabRecorder).

Usage:  python get_openmct.py [--version 4.3.1]
"""
import argparse
import io
import sys
import tarfile
import urllib.request
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", default="4.3.1")
    args = ap.parse_args()

    url = f"https://registry.npmjs.org/openmct/-/openmct-{args.version}.tgz"
    dest = WEB / "openmct"
    print(f"Downloading {url} ...")
    data = urllib.request.urlopen(url, timeout=120).read()
    print(f"  {len(data) // 1024 // 1024} MB; extracting dist/ -> {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            # package/dist/<path> -> web/openmct/<path>
            if not m.name.startswith("package/dist/") or not m.isfile():
                continue
            rel = Path(m.name).relative_to("package/dist")
            out = dest / rel
            if not str(out.resolve()).startswith(str(dest.resolve())):
                continue  # path traversal guard
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(tf.extractfile(m).read())
            n += 1
    print(f"Done: {n} files. The console now works fully offline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
