# multi_cam_record_headless.py
import os, threading, signal, sys, time
import pyzed.sl as sl

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
    finally:
        cam.disable_recording(); cam.close()
        print(f"[{serial}] stopped after {frames} frames")

def main():
    devs = sl.Camera.get_device_list()
    if not devs:
        print("No ZED devices found."); return 1
    out_dir = os.path.expanduser("~/zed_rec")

    threads=[]
    for d in devs:
        t = threading.Thread(target=record_one, args=(d.serial_number, out_dir))
        t.start(); threads.append(t)

    print("Recording... Ctrl+C to stop")
    for t in threads: t.join()
    return 0

if __name__ == "__main__":
    sys.exit(main())
