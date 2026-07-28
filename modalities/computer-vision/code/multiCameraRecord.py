# multi_cam_record_headless.py
import os, threading, signal, sys, time, json
from datetime import datetime
import pyzed.sl as sl

# ---------------------------------------------------------------------------
# Camera labelling
# ---------------------------------------------------------------------------
# Map each physical camera's serial number to a stable label ("cam1"/"cam2").
# This keeps "camera 1" and "camera 2" pinned to the same physical device
# across runs, regardless of the (unstable) order get_device_list() returns.
#
# The real serial->label map lives in a camera_roles.json deployed next to
# this script (gitignored — full serials stay out of the public repo, see
# docs/identifiers.md rule 4), e.g. {"12345678": "cam1", "87654321": "cam2"}.
# Serials are printed at startup and shown in the ZED_Explorer tool.
CAMERA_LABELS = {
    # <serial_number>: "<label>",  — placeholders; overridden by camera_roles.json
    111111111: "cam1",
    222222222: "cam2",
}

_ROLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "camera_roles.json")
if os.path.exists(_ROLES_PATH):
    with open(_ROLES_PATH) as _f:
        CAMERA_LABELS.update({int(k): str(v) for k, v in json.load(_f).items()})

def label_for(serial):
    """Return the stable label for a serial, or a safe serial-based fallback."""
    # Fallback keeps recordings uniquely named even if the serial isn't mapped
    # yet, so nothing is ever overwritten while CAMERA_LABELS is unfilled.
    return CAMERA_LABELS.get(serial, f"cam-SN{serial}")

STOP = False
def on_sigint(sig, frame):
    global STOP; STOP = True
signal.signal(signal.SIGINT, on_sigint)

# Fusion needs every camera's data, so one camera dying mid-session makes the
# rest of the recording useless on its own. ~3s of consecutive grab failures
# (rather than a single blip) trips this, then all cameras stop together
# instead of one camera silently recording alone for the rest of the session.
MAX_CONSECUTIVE_GRAB_FAILURES = 90

def open_camera(serial, fps=30):
    # Opening a ZED camera is NOT safe to race across threads — the first
    # open() in a process does GPU/CUDA context init, and opening multiple
    # cameras concurrently from separate threads can make every open() fail
    # at once ("Camera::open() has not been called" style errors on all
    # cameras). Cameras must be opened one at a time in a single thread;
    # only the grab loop afterward is safe to parallelize.
    init = sl.InitParameters()
    init.set_from_serial_number(serial)
    init.camera_resolution = sl.RESOLUTION.AUTO
    init.camera_fps = fps
    init.depth_mode = sl.DEPTH_MODE.NONE  # pure recording needs no depth; set NEURAL/PERFORMANCE if you add depth later

    cam = sl.Camera()
    err = cam.open(init)
    return cam, err

def record_one(cam, serial, label, out_dir, session_stamp):
    global STOP
    # Filename: <label>_<date>_<time>.svo2  e.g. cam1_2026-07-01_14-32-05.svo2
    # - label ("cam1"/"cam2") separates the cameras
    # - the shared session date+time stamp prevents overwriting prior videos
    #   and lets you pair cam1/cam2 from the same run (identical stamp)
    fname = f"{label}_{session_stamp}.svo2"
    out_path = os.path.join(out_dir, fname)
    rec = sl.RecordingParameters(out_path, sl.SVO_COMPRESSION_MODE.H265)
    if cam.enable_recording(rec) != sl.ERROR_CODE.SUCCESS:
        print(f"[{serial}] ({label}) enable_recording failed"); cam.close()
        STOP = True  # this camera never started; the rest of the rig alone isn't useful for fusion
        return
    print(f"[{serial}] ({label}) recording to {out_path}")

    rt = sl.RuntimeParameters()
    consecutive_failures = 0
    try:
        while not STOP:
            # The Python SDK only writes a frame when grab() returns SUCCESS.
            # Check the return code so failures are logged instead of silently
            # spinning the CPU as fast as possible.
            err = cam.grab(rt)
            if err != sl.ERROR_CODE.SUCCESS:
                consecutive_failures += 1
                print(f"[{serial}] ({label}) grab failed: {err} ({consecutive_failures} in a row)")
                if consecutive_failures >= MAX_CONSECUTIVE_GRAB_FAILURES:
                    print(f"[{serial}] ({label}) too many consecutive grab failures — stopping all cameras.")
                    STOP = True
                    break
                time.sleep(0.005)  # brief backoff to avoid a busy-spin on repeated failures
            else:
                consecutive_failures = 0
    finally:
        cam.disable_recording(); cam.close()
        print(f"[{serial}] ({label}) stopped")

def main():
    devs = sl.Camera.get_device_list()
    if not devs:
        print("No ZED devices found."); return 1

    # Output location, stated explicitly and logged so it's easy to find.
    out_dir = os.path.expanduser("~/zed_rec")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Saving recordings to: {out_dir}")

    # One timestamp for the whole session so cam1/cam2 files line up.
    session_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Open every camera sequentially, in this thread, before starting any
    # grab loops — see the note in open_camera() for why this can't be
    # parallelized.
    opened = []
    for d in devs:
        serial = d.serial_number
        label = label_for(serial)
        print(f"Detected camera serial {serial} -> {label}")
        cam, err = open_camera(serial)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f"[{serial}] ({label}) open failed: {err}")
            continue
        opened.append((cam, serial, label))

    if not opened:
        print("No cameras opened successfully."); return 1
    if len(opened) < len(devs):
        print(f"WARNING: only {len(opened)}/{len(devs)} cameras opened — continuing with the rest.")

    threads=[]
    for cam, serial, label in opened:
        t = threading.Thread(target=record_one, args=(cam, serial, label, out_dir, session_stamp))
        t.start(); threads.append(t)

    print("Recording... Ctrl+C to stop")
    for t in threads: t.join()
    return 0

if __name__ == "__main__":
    sys.exit(main())