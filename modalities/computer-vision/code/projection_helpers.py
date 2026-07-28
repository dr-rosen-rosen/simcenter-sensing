# projection_helpers.py
import json
import numpy as np

# ---------- Matrix helpers ----------
def invert_se3(Twc: np.ndarray) -> np.ndarray:
    """Invert 4x4 SE3 (world_T_cam -> cam_T_world)."""
    R = Twc[:3,:3]
    t = Twc[:3, 3]
    Ri = R.T
    ti = -Ri @ t
    Tcw = np.eye(4)
    Tcw[:3,:3] = Ri
    Tcw[:3, 3] = ti
    return Tcw

def project_point(K, Tcw, Pw):
    """Project world point Pw (3,) to pixel (u,v). Returns (u,v,z_cam)."""
    Pw_h = np.array([Pw[0], Pw[1], Pw[2], 1.0], dtype=float)
    Pc = (Tcw @ Pw_h)[:3]  # camera coords
    z = Pc[2]
    if z <= 1e-6:
        return None  # behind camera
    u = K[0,0] * (Pc[0] / z) + K[0,2]
    v = K[1,1] * (Pc[1] / z) + K[1,2]
    return (float(u), float(v), float(z))

def make_K(fx, fy, cx, cy):
    K = np.eye(3, dtype=float)
    K[0,0] = fx; K[1,1] = fy
    K[0,2] = cx; K[1,2] = cy
    return K

# ---------- Loaders ----------
def load_extrinsics_from_fusion_conf(conf_path: str):
    """
    Parse a Stereolabs Fusion calibration file and return:
      serial -> world_T_cam (4x4)

    Handles two layouts:

    1) ZED360 export (what the ZED360 tool actually writes) — a dict keyed by
       serial, each value holding a "FusionConfiguration" with a flat 16-value
       row-major 4x4 "pose" string:
         { "44429816": { "FusionConfiguration": {
               "pose": "1 0 0 0  0 1 0 -1.36  0 0 1 0  0 0 0 1",
               "serial_number": 44429816, ... } }, ... }

    2) A generic list layout (kept for compatibility / hand-authored files):
         { "cameras": [
             { "serial_number": 444..., "pose": {"rotation": [[..],[..],[..]],
                                                 "translation":[x,y,z]} }, ... ] }
    """
    with open(conf_path, "r") as f:
        data = json.load(f)

    serial_to_Twc = {}
    if not isinstance(data, dict):
        return serial_to_Twc

    # --- Layout 1: ZED360 serial-keyed dict with FusionConfiguration ---
    for key, val in data.items():
        if not isinstance(val, dict):
            continue
        fc = val.get("FusionConfiguration")
        if not isinstance(fc, dict):
            continue
        pose = fc.get("pose")
        sn = fc.get("serial_number", key)
        Twc = _twc_from_pose_string(pose)
        if Twc is None:
            continue
        try:
            serial_to_Twc[int(sn)] = Twc
        except (TypeError, ValueError):
            continue
    if serial_to_Twc:
        return serial_to_Twc

    # --- Layout 2: generic list of cameras/sensors ---
    candidates = []
    if "cameras" in data and isinstance(data["cameras"], list):
        candidates = data["cameras"]
    elif "sensors" in data and isinstance(data["sensors"], list):
        candidates = data["sensors"]

    for cam in candidates:
        # serial
        sn = cam.get("serial_number") or cam.get("serial") or cam.get("id")
        # pose
        pose = cam.get("pose") or cam.get("transform") or cam.get("extrinsics")
        if sn is None or pose is None:
            continue
        R = pose.get("rotation")
        t = pose.get("translation")
        if R is None or t is None:
            continue
        R = np.array(R, dtype=float).reshape(3,3)
        t = np.array(t, dtype=float).reshape(3)
        Twc = np.eye(4, dtype=float)
        Twc[:3,:3] = R
        Twc[:3, 3] = t
        serial_to_Twc[int(sn)] = Twc
    return serial_to_Twc


def _twc_from_pose_string(pose):
    """Parse a ZED360 flat pose into a 4x4 world_T_cam, or None if unparseable.

    The pose is 16 whitespace-separated floats in row-major order (a full 4x4
    homogeneous transform). Accepts a already-numeric 16-length sequence too.
    """
    if pose is None:
        return None
    try:
        if isinstance(pose, str):
            vals = [float(x) for x in pose.split()]
        else:
            vals = [float(x) for x in pose]
    except (TypeError, ValueError):
        return None
    if len(vals) != 16:
        return None
    return np.array(vals, dtype=float).reshape(4, 4)

def intrinsics_from_caminfo(cam_info) -> dict:
    """
    Build intrinsics map: serial -> K (3x3).
    Uses LEFT camera intrinsics for projection onto the LEFT view (what you draw on).
    """
    serial = int(cam_info.serial_number)
    calib  = cam_info.camera_configuration.calibration_parameters
    left   = calib.left_cam  # has fx, fy, cx, cy
    K = make_K(left.fx, left.fy, left.cx, left.cy)
    return {serial: K}