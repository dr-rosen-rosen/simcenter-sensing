# multi_cam_record_headless.py
import os, threading, signal, sys, time
import urllib.request
import pyzed.sl as sl

# Preview frames to the session console (optional, opt-in): set
# ZED_CONSOLE_HOST to the analysis laptop's IP to push ~1 Hz downscaled
# JPEGs to the console's imagery view. Requires cv2 (present in ZED_env).
# Failures are swallowed: previews must never interrupt recording.
CONSOLE_HOST = os.environ.get("ZED_CONSOLE_HOST")
PREVIEW_EVERY = 30   # one preview per N successful grabs (~1 Hz at 30 fps)
PREVIEW_WIDTH = 640
try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

# LSL frame markers are optional: recording must never depend on them.
# To enable on the ZedBox: `pip install pylsl` inside ZED_env.
try:
    from pylsl import StreamInfo, StreamOutlet
    LSL_OK = True
except ImportError:
    LSL_OK = False

MARKER_EVERY = 30  # one LSL marker per N successful grabs (~1 Hz at 30 fps)

STOP = False
def on_sigint(sig, frame):
    global STOP; STOP = True
signal.signal(signal.SIGINT, on_sigint)

def record_one(serial, out_dir, fps=30):
    init = sl.InitParameters()
    init.set_from_serial_number(serial)
    init.camera_resolution = sl.RESOLUTION.AUTO
    init.camera_fps = fps
    init.depth_mode = sl.DEPTH_MODE.NEURAL  # switch to PERFORMANCE if you want depth later

    cam = sl.Camera()
    if cam.open(init) != sl.ERROR_CODE.SUCCESS:
        print(f"[{serial}] open failed"); return

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{serial}.svo2")
    rec = sl.RecordingParameters(out_path, sl.SVO_COMPRESSION_MODE.H265)
    if cam.enable_recording(rec) != sl.ERROR_CODE.SUCCESS:
        print(f"[{serial}] enable_recording failed"); cam.close(); return
    print(f"[{serial}] recording to {out_path}")

    # LSL outlet publishing "serial=<s> frame=<n> cam_ts_ns=<t>" markers,
    # giving a continuous ZED-clock <-> LSL-clock mapping for alignment.
    outlet = None
    if LSL_OK:
        info = StreamInfo(f"simcenter.zed.{serial}", "Markers", 1, 0,
                          "string", f"zed-{serial}")
        outlet = StreamOutlet(info)
        print(f"[{serial}] LSL frame markers on (every {MARKER_EVERY} frames)")
    else:
        print(f"[{serial}] pylsl not installed - recording without LSL markers")

    preview = bool(CONSOLE_HOST and CV2_OK)
    if CONSOLE_HOST and not CV2_OK:
        print(f"[{serial}] ZED_CONSOLE_HOST set but cv2 missing - no previews")
    if preview:
        print(f"[{serial}] console previews on -> {CONSOLE_HOST}:8300 (every {PREVIEW_EVERY} frames)")
        preview_mat = sl.Mat()

    rt = sl.RuntimeParameters()
    frames = 0
    try:
        while not STOP:
            if cam.grab(rt) != sl.ERROR_CODE.SUCCESS:  # SDK writes frames on each successful grab
                continue
            frames += 1
            if outlet and frames % MARKER_EVERY == 0:
                try:
                    ts_ns = cam.get_timestamp(sl.TIME_REFERENCE.IMAGE).get_nanoseconds()
                    outlet.push_sample([f"serial={serial} frame={frames} cam_ts_ns={ts_ns}"])
                except Exception:
                    pass  # LSL must never interrupt recording
            if preview and frames % PREVIEW_EVERY == 0:
                try:
                    cam.retrieve_image(preview_mat, sl.VIEW.LEFT)
                    img = preview_mat.get_data()[:, :, :3]
                    h, w = img.shape[:2]
                    small = cv2.resize(img, (PREVIEW_WIDTH, int(h * PREVIEW_WIDTH / w)))
                    ok, buf = cv2.imencode(".jpg", small,
                                           [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                    if ok:
                        req = urllib.request.Request(
                            f"http://{CONSOLE_HOST}:8300/api/frame?source=zed-{serial}",
                            data=buf.tobytes(), method="POST")
                        urllib.request.urlopen(req, timeout=1.0)
                except Exception:
                    pass  # previews must never interrupt recording
    finally:
        cam.disable_recording(); cam.close()
        print(f"[{serial}] stopped after {frames} frames")

def main():
    devs = sl.Camera.get_device_list()
    if not devs:
        print("No ZED devices found."); return 1
    # Per-run subdirectory: a fixed path would silently overwrite the
    # previous session's SVO2s if offload hadn't happened yet.
    out_dir = os.path.expanduser(time.strftime("~/zed_rec/%Y%m%d-%H%M%S"))
    print(f"Session output dir: {out_dir}")

    threads=[]
    for d in devs:
        t = threading.Thread(target=record_one, args=(d.serial_number, out_dir))
        t.start(); threads.append(t)

    print("Recording... Ctrl+C to stop")
    for t in threads: t.join()
    return 0

if __name__ == "__main__":
    sys.exit(main())
