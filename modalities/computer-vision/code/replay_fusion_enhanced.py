#!/usr/bin/env python3
"""
Offline fusion + analytics for two ZED X SVO/SVO2 recordings.

Features:
- Opens 2 SVOs in playback, enables body tracking on each client, publishes locally.
- Starts Fusion and retrieves *fused* 3D skeletons in WORLD coordinates.
- Computes per-person per-joint velocity & acceleration (finite differences).
- Optionally extracts 2D "head-ish" crops per person (from 2D body bbox) for a gaze model.
- Optionally writes annotated demo videos (one per camera) with 2D skeletons + gaze arrows.

IMPORTANT:
- This draws 2D overlays from each camera's *local* body tracking (not fused)
  for video demos, to avoid heavy per-frame 3D→2D projection code.
- CSV contains the *fused* 3D tracks with kinematics.

Fill in SVO paths and Fusion calibration path below.
"""

import os, sys, csv, math, time
from collections import defaultdict, deque, Counter

import pyzed.sl as sl
import numpy as np
import cv2
from gaze_geometry import compute_head_frame_world
from projection_helpers import (
    load_extrinsics_from_fusion_conf, intrinsics_from_caminfo,
    invert_se3, project_point
)
from arm_joint_angles import (
    compute_arm_angles, csv_angle_columns, get_arm_indices, AngleSmoother
)

# -------------------- USER CONFIG --------------------
SVO_FILES = [
    "/home/user/zed_rec/44429816.svo2",
    "/home/user/zed_rec/45817796.svo2",
]
FUSION_CONF = "/home/user/zed_rec/fusion_calibration.json"
OUT_CSV     = "/home/user/zed_rec/fused_bodies.csv"

# Depth / body tracking (used at replay time)
DEPTH_MODE  = sl.DEPTH_MODE.NEURAL     # ULTRA/NEURAL for accuracy; PERFORMANCE for speed
BODY_MODEL  = sl.BODY_TRACKING_MODEL.HUMAN_BODY_MEDIUM  # FAST/MEDIUM/ACCURATE
BODY_FORMAT = sl.BODY_FORMAT.BODY_34  # BODY_38 if you need extra extremities

# World coordinate convention. MUST match whatever frame the fusion_calibration
# extrinsics (ZED360 output) were expressed in, and MUST be identical between
# every camera client and Fusion itself -- if it's wrong, each camera's local
# skeleton lands in a different (wrong) part of world space and Fusion creates
# a separate person track per camera instead of merging them into one.
#
# IMAGE was determined empirically (2026-07-27) against a real two-camera
# recording + ZED360 calibration: it was the only RIGHT-HANDED convention
# (of 6 tested) that merged both cameras' view of one real person into a
# single fused person_id across the whole clip; every RIGHT_HANDED_*_UP
# variant fragmented one person into 2-3 person_ids. LEFT_HANDED_Y_UP also
# merged correctly, but is left-handed, which would silently flip the sign of
# forward/backward and left/right in arm_joint_angles.py's cross-product-based
# anatomical frame -- IMAGE avoids that without touching the angle math.
# See changes.txt (2026-07-27, "coordinate-system mismatch") for the sweep.
COORD_SYSTEM = sl.COORDINATE_SYSTEM.IMAGE

# Kinematics
KINEMATICS_ENABLED   = True
VEL_ACC_WINDOW       = 2      # use 2-frame window for finite difference (previous/current)
MAX_HISTORY          = 5      # per person history for smoothing/robustness

# Arm joint angles (elbow + shoulder), computed from the fused 3D skeleton
ARM_ANGLES_ENABLED   = True
ARM_CONF_THRESHOLD   = 0.0    # drop joints below this per-keypoint confidence (fused conf scale)
ARM_SMOOTH_WINDOW    = 0      # >1 enables temporal smoothing of the angle streams

# Head crops & gaze
SAVE_HEAD_CROPS      = True
HEAD_CROP_DIR        = "/home/user/zed_rec/head_crops"
CROP_SIZE            = 224    # resize crops to this square
RUN_GAZE_MODEL       = False  # set True after you plug a model into GazeEstimator.predict()
GAZE_RAY_LENGTH_M    = 2.0    # length of drawn gaze ray in meters (for 3D), used only if projecting

# Demo videos (2D overlays from each camera’s own tracking)
WRITE_DEMO_VIDEOS    = True
VIDEO_DIR            = "/home/user/zed_rec/demos"
VIDEO_FPS_OVERRIDE   = None   # None → use SVO fps; or set e.g. 30
VIDEO_SCALE          = 0.75   # resize frames for lighter output

# -----------------------------------------------------

class GazeEstimator:
    """
    Placeholder for a gaze model (e.g., Gaze360).
    Implement `predict(face_bgr)` to return a unit gaze vector in the camera frame (dx,dy,dz).
    Return None to skip drawing.
    """
    def __init__(self):
        # load your Torch/TensorRT model here
        self.ready = False

    def predict(self, face_bgr: np.ndarray):
        if not self.ready:
            return None
        # TODO: run your model; return np.array([dx, dy, dz]) with ||v||=1
        return None

def open_client_from_svo(svo_path, depth_mode=sl.DEPTH_MODE.NEURAL, fps=None):
    cam = sl.Camera()
    init = sl.InitParameters()
    init.set_from_svo_file(svo_path)
    init.depth_mode = depth_mode
    init.svo_real_time_mode = False   # offline faster-than-real-time
    # Match the Fusion coordinate frame/units so published bodies line up with
    # the fused world (Fusion is initialized with the same COORD_SYSTEM below).
    init.coordinate_units  = sl.UNIT.METER
    init.coordinate_system = COORD_SYSTEM

    if fps: init.camera_fps = fps
    err = cam.open(init)
    if err != sl.ERROR_CODE.SUCCESS:
        print(f"[CLIENT] Failed to open {svo_path}: {err}")
        return None

    # NEW: positional tracking must be enabled before body tracking
    pt = sl.PositionalTrackingParameters()
    pt.set_as_static = True              # fixed cams during recording
    pt.enable_pose_smoothing = True
    err = cam.enable_positional_tracking(pt)
    if err != sl.ERROR_CODE.SUCCESS:
        print("[CLIENT] enable_positional_tracking failed:", err)
        cam.close()
        return None

    return cam

def enable_bt_and_publish(cam: sl.Camera):
    p = sl.BodyTrackingParameters()
    p.enable_tracking = True
    p.enable_body_fitting = True
    p.body_format = BODY_FORMAT
    p.detection_model = BODY_MODEL
    err = cam.enable_body_tracking(p)
    if err != sl.ERROR_CODE.SUCCESS:
        print("[CLIENT] Body tracking enable failed:", err)
        return False
    # publish to local shared memory (intra-host)
    cp = sl.CommunicationParameters()
    cp.set_for_shared_memory()
    cam.start_publishing(cp)
    return True

# --- replace your init_fusion(...) and camera-registration bits with this ---

def _transform_from_matrix(Twc):
    """Build an sl.Transform from a 4x4 numpy world_T_cam (identity if None)."""
    T = sl.Transform()
    if Twc is None:
        T.set_identity()
        return T
    m4 = sl.Matrix4f()
    for r in range(4):
        for c in range(4):
            m4[r, c] = float(Twc[r, c])
    T.init_matrix(m4)
    return T

def init_fusion():
    fusion = sl.Fusion()
    fparams = sl.InitFusionParameters()
    fparams.coordinate_units  = sl.UNIT.METER
    fparams.coordinate_system = COORD_SYSTEM

    # Fusion methods return FUSION_ERROR_CODE (a distinct enum from ERROR_CODE).
    err = fusion.init(fparams)
    if err != sl.FUSION_ERROR_CODE.SUCCESS:
        print("[FUSION] init failed:", err)
        return None
    else:
        print("[FUSION] init SUCCESS")
    return fusion

def enable_fusion_body_tracking(fusion):
    """Enable body-tracking fusion. MUST be called AFTER the cameras are
    subscribed, so Fusion can resolve the senders' body format (otherwise it
    returns WRONG BODY FORMAT)."""
    bt = sl.BodyTrackingFusionParameters()
    bt.enable_tracking = True
    bt.enable_body_fitting = True
    err = fusion.enable_body_tracking(bt)
    if err != sl.FUSION_ERROR_CODE.SUCCESS:
        print("[FUSION] enable_body_tracking failed:", err)
        return False
    return True

def add_inputs_to_fusion(fusion, serials, Twc_map):
    """
    Register (subscribe) each publishing camera with Fusion over shared memory,
    supplying its world pose (world_T_cam) from the calibration when available.
    """
    for sn in serials:
        # identify the sender by serial so Fusion matches it to the publisher
        uuid = sl.CameraIdentifier()
        uuid.serial_number = sn

        # transport: shared memory on the same host
        rx = sl.CommunicationParameters()
        rx.set_for_shared_memory()

        # camera world pose (identity if we have no calibration for this serial)
        Twc = Twc_map.get(sn, None)
        pose = _transform_from_matrix(Twc)

        err = fusion.subscribe(uuid, rx, pose)
        if err != sl.FUSION_ERROR_CODE.SUCCESS:
            print(f"[FUSION] subscribe({sn}) failed:", err)
            return False
    return True

def _report_person_summary(person_frames, person_head_sum, total_frames):
    """Print per-person coverage and warn if one subject looks fragmented.

    A coordinate-system mismatch between the ZED360 calibration and
    COORD_SYSTEM makes Fusion reconstruct each camera's view of the SAME
    person into a different part of world space, so it emits several
    person_ids instead of one. That failure is silent in the CSV -- every row
    looks confident and well-formed -- so surface it here. See changes.txt
    (2026-07-27, coordinate-system mismatch).
    """
    if not person_frames:
        print("[PEOPLE] no fused bodies were produced")
        return
    print(f"[PEOPLE] {len(person_frames)} fused person_id(s) over {total_frames} frames:")
    for pid, n in sorted(person_frames.items()):
        cov = (100.0 * n / total_frames) if total_frames else 0.0
        head = person_head_sum.get(pid)
        where = ""
        if head is not None and n:
            m = head / n
            where = f"  mean head=({m[0]:.2f}, {m[1]:.2f}, {m[2]:.2f}) m"

        print(f"         person {pid}: {n} frames ({cov:.0f}% coverage){where}")

    if len(person_frames) > 1:
        print("[PEOPLE] WARNING: more than one person was tracked.")
        print("         If only ONE person was in the room, this is very likely a")
        print("         coordinate-system mismatch, not two subjects: check a demo")
        print("         video, then run diagnose_fusion_frame.py to find the")
        print("         COORD_SYSTEM that merges them into a single person_id.")


def write_csv_header(writer, kp_count):
    cols = ["timestamp_ns","person_id","confidence","tracking_state"]
    for i in range(kp_count):
        cols += [f"k{i}_x","k{i}_y","k{i}_z"]
    if KINEMATICS_ENABLED:
        for i in range(kp_count):
            cols += [f"k{i}_vx","k{i}_vy","k{i}_vz",
                     f"k{i}_ax","k{i}_ay","k{i}_az"]
    cols += ["head_x","head_y","head_z","gaze_dx","gaze_dy","gaze_dz"]
    if ARM_ANGLES_ENABLED:
        cols += csv_angle_columns()
    writer.writerow(cols)

def compute_vel_acc(prev_pts, prev_t, pts, t, prev_vel=None):
    """
    prev_pts, pts: (K,3) arrays in meters (WORLD)
    t, prev_t: nanoseconds
    prev_vel: (K,3) velocity from the previous frame, or None on the first frame.
    Returns vel, acc as (K,3) arrays; if not enough history, zeros.
    """
    if prev_pts is None or prev_t is None or t == prev_t:
        z = np.zeros_like(pts)
        return z, z
    dt = (t - prev_t) * 1e-9  # seconds
    v = (pts - prev_pts) / max(dt, 1e-6)
    # Acceleration = change in velocity over the same dt. Needs a previous
    # velocity; on the first usable frame we don't have one yet, so return zeros.
    if prev_vel is None:
        a = np.zeros_like(v)
    else:
        a = (v - prev_vel) / max(dt, 1e-6)
    return v, a

def draw_2d_skeleton(frame_bgra, body, color=(0,255,0)):
    """
    Draws a simple scatter/line skeleton using 2D keypoints.
    Assumes body.keypoint_2d is (K,2).
    """
    if body.keypoint_2d is None: return frame_bgra
    pts = np.array(body.keypoint_2d).astype(int)
    for (x,y) in pts:
        cv2.circle(frame_bgra, (x,y), 3, color, -1)
    # Minimal connecting lines (if available). Without an explicit topology, we skip lines.
    return frame_bgra

def extract_head_crop(frame_bgra, body, crop_size=224, expand=0.25):
    """
    Use the 2D body bounding box to crop an upper region as a proxy for head.
    This is a heuristic; for higher fidelity use a face detector.
    """
    if body.bounding_box_2d is None or len(body.bounding_box_2d) == 0:
        return None
    h, w = frame_bgra.shape[:2]
    bb = np.array(body.bounding_box_2d).astype(int)  # 4 corners (x,y)
    x0 = bb[:,0].min(); y0 = bb[:,1].min()
    x1 = bb[:,0].max(); y1 = bb[:,1].max()
    # take upper third as "head-ish" region
    y_head1 = y0
    y_head2 = y0 + int((y1-y0)*0.35)
    # expand a bit
    pad_x = int((x1-x0)*expand)
    pad_y = int((y_head2-y_head1)*expand)
    x0p = max(0, x0 - pad_x); x1p = min(w, x1 + pad_x)
    y0p = max(0, y_head1 - pad_y); y1p = min(h, y_head2 + pad_y)
    if x1p <= x0p or y1p <= y0p:
        return None
    crop = frame_bgra[y0p:y1p, x0p:x1p, :3]  # BGR (drop alpha)
    if crop.size == 0: return None
    crop = cv2.resize(crop, (crop_size, crop_size), interpolation=cv2.INTER_LINEAR)
    return crop

def annotate_gaze(frame_bgra, origin_px, gaze_cam_dir, scale_px=80, color=(0,0,255)):
    """
    Draw a 2D arrow from origin in image pixels using a *camera-frame* gaze direction.
    This assumes you derived a 2D direction in image space or a rough mapping.
    Here we simply draw a short arrow in the local +x/-y heuristic for demo.
    For real projection, map 3D ray through camera intrinsics.
    """
    if origin_px is None or gaze_cam_dir is None:
        return frame_bgra
    ox, oy = int(origin_px[0]), int(origin_px[1])
    dx, dy, dz = gaze_cam_dir
    # crude: project (dx, dy) to image plane sign-wise (for demo arrows)
    ex = int(ox + dx * scale_px)
    ey = int(oy - dy * scale_px)
    cv2.arrowedLine(frame_bgra, (ox,oy), (ex,ey), color, 2, tipLength=0.2)
    return frame_bgra

def process_session(svo_files, fusion_conf, out_csv, head_crop_dir=None, video_dir=None):
    """Run fusion + angle processing for one cam1/cam2 SVO2 pair. Everything
    that's fixed dataset-wide (body model, depth mode, angle/video toggles,
    etc.) stays a module-level constant above; only the per-session paths
    are parameters, so batch_process_sessions.py can call this in a loop
    without touching the USER CONFIG block."""
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    if SAVE_HEAD_CROPS: os.makedirs(head_crop_dir, exist_ok=True)
    if WRITE_DEMO_VIDEOS: os.makedirs(video_dir, exist_ok=True)

    # 1) Open clients, enable BT + publishers
    clients = []
    for p in svo_files:
        cam = open_client_from_svo(p, DEPTH_MODE)
        if cam is None: 
            print("Failed to open:", p); return 1
        if not enable_bt_and_publish(cam):
            print("Body tracking publish failed:", p); return 1
        clients.append(cam)

    # 2) Prepare per-client display and writers (optional videos)
    mats = [sl.Mat() for _ in clients]
    rt   = [sl.RuntimeParameters() for _ in clients]
    writers = [None]*len(clients)
    info = [c.get_camera_information() for c in clients]
    
    # Build intrinsics per serial from the actual SVO camera calibration
    K_map = {}
    serials = []
    for i in info:
        serials.append(int(i.serial_number))
        K_map.update(intrinsics_from_caminfo(i))

    # Load world_T_cam from fusion calibration file
    Twc_map = load_extrinsics_from_fusion_conf(fusion_conf)
    # Precompute cam_T_world for quick projection
    Tcw_map = {}
    for sn in serials:
        Twc = Twc_map.get(sn)
        if Twc is None:
            print(f"[WARN] No extrinsics in fusion conf for serial {sn}. Using identity (world==cam).")
            Twc = np.eye(4)
        Tcw_map[sn] = invert_se3(Twc)
    fpss = [i.camera_configuration.fps for i in info]
    widths = [i.camera_configuration.resolution.width for i in info]
    heights= [i.camera_configuration.resolution.height for i in info]
    out_sizes = [None]*len(clients)   # per-camera (out_w, out_h); avoids one camera's size leaking to another
    for idx, cam in enumerate(clients):
        # --- writer creation ---
        if WRITE_DEMO_VIDEOS:
            fps = VIDEO_FPS_OVERRIDE or int(round(fpss[idx]))
            out_w, out_h = int(widths[idx]*VIDEO_SCALE), int(heights[idx]*VIDEO_SCALE)
            out_sizes[idx] = (out_w, out_h)

            # robust choice on Jetson:
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            out_path = os.path.join(video_dir, f"demo_cam{idx+1}.avi")
            w = cv2.VideoWriter(out_path, fourcc, fps, (out_w, out_h))
            writers[idx] = w
            if not w.isOpened():
                print(f"[VIDEO][cam{idx+1}] FAILED to open writer {out_path}")
            else:
                print(f"[VIDEO][cam{idx+1}] Writing {out_path} @ {fps} FPS, size=({out_w},{out_h})")

    # 3) Fusion init -> subscribe cameras -> enable body tracking (order matters)
    fusion = init_fusion()
    if fusion is None: return 1
    # Register each camera with Fusion (shared memory transport + optional world pose)
    if not add_inputs_to_fusion(fusion, serials, Twc_map):
        return 1
    # Enable body-tracking fusion only after senders are subscribed.
    if not enable_fusion_body_tracking(fusion):
        return 1

    # 4) CSV setup
    kp_count = 34 if BODY_FORMAT == sl.BODY_FORMAT.BODY_34 else 38
    bf_str   = "BODY_34" if BODY_FORMAT == sl.BODY_FORMAT.BODY_34 else "BODY_38"
    # Arm-angle setup: resolve joint indices once and (optionally) build a smoother.
    arm_idx      = get_arm_indices(bf_str) if ARM_ANGLES_ENABLED else None
    arm_cols     = csv_angle_columns() if ARM_ANGLES_ENABLED else []
    arm_smoother = AngleSmoother(ARM_SMOOTH_WINDOW) if (ARM_ANGLES_ENABLED and ARM_SMOOTH_WINDOW > 1) else None
    csvf = open(out_csv, "w", newline="")
    writer = csv.writer(csvf)
    write_csv_header(writer, kp_count)

    # kinematics buffers
    prev_pts   = {}   # person_id -> (K,3)
    prev_time  = {}   # person_id -> ns
    prev_vel   = {}   # person_id -> (K,3) previous velocity, for acceleration
    # optional: maintain short histories to estimate acceleration better
    v_hist = defaultdict(lambda: deque(maxlen=MAX_HISTORY))

    # Gaze model
    gaze = GazeEstimator()

    # 5) Playback loop
    body_fusion_rt = sl.BodyTrackingFusionRuntimeParameters()
    active = True
    frame_idx = 0
    # Per-person frame counts + mean head position, used for the post-run
    # fragmentation check (see _report_person_summary).
    person_frames = Counter()
    person_head_sum = defaultdict(lambda: np.zeros(3))
    try:
        while active:
            active = False

            # Step each client once; also retrieve local bodies & image for video
            local_bodies = []
            frames_bgra  = []
            for i, cam in enumerate(clients):
                err = cam.grab(rt[i])
                # SVO end?
                if err not in (sl.ERROR_CODE.SUCCESS, sl.ERROR_CODE.END_OF_SVOFILE_REACHED):
                    continue
                if err == sl.ERROR_CODE.SUCCESS:
                    active = True
                    # retrieve image + local bodies (for 2D overlay)
                    cam.retrieve_image(mats[i], sl.VIEW.LEFT)  # BGRA
                    frames_bgra.append(mats[i].get_data().copy())
                    bodies = sl.Bodies()
                    cam.retrieve_bodies(bodies)
                    local_bodies.append(bodies)
                else:
                    frames_bgra.append(None)
                    local_bodies.append(sl.Bodies())

            # Reset the per-frame head/gaze map up front so the demo-video block
            # below always sees a defined value, even on frames with no fused
            # bodies or when fusion.process() did not return SUCCESS.
            fused_head_gaze = {}   # pid -> (head_world(3,), gaze_dir_world(3,))

            # Ingest the latest published frames and retrieve the fused bodies.
            if fusion.process() == sl.FUSION_ERROR_CODE.SUCCESS:
                fused = sl.Bodies()
                fusion.retrieve_bodies(fused, body_fusion_rt)
                ts_ns = fused.timestamp.get_nanoseconds()

                # One pass per fused body. Every column in `row` — keypoints,
                # kinematics, head and gaze — is derived from THIS same body, so
                # they stay matched to one person. (The previous version rebuilt
                # head/gaze in a nested loop that clobbered the loop variable and
                # wrote the last body's head/gaze onto every row.)
                for b in fused.body_list:
                    pid = b.id
                    kp = np.asarray(b.keypoint, dtype=np.float32)  # (K,3) WORLD
                    # tracking_state is an OBJECT_TRACKING_STATE enum in SDK 5.x;
                    # take .value (fall back to the raw value if already numeric).
                    ts_state = getattr(b.tracking_state, "value", b.tracking_state)
                    row = [ts_ns, pid, float(b.confidence), int(ts_state)]
                    for p in kp:
                        row.extend([float(p[0]), float(p[1]), float(p[2])])

                    if KINEMATICS_ENABLED:
                        v, a = compute_vel_acc(prev_pts.get(pid), prev_time.get(pid),
                                               kp, ts_ns, prev_vel.get(pid))
                        # smoothing: median velocity over a short window
                        v_hist[pid].append(v)
                        v_smooth = np.median(np.stack(v_hist[pid], axis=0), axis=0) if len(v_hist[pid])>1 else v
                        for p in v_smooth: row.extend([float(p[0]), float(p[1]), float(p[2])])
                        for p in a:        row.extend([float(p[0]), float(p[1]), float(p[2])])
                        prev_pts[pid]  = kp
                        prev_time[pid] = ts_ns
                        prev_vel[pid]  = v

                    # Head frame + gaze for THIS body, matched to its own row.
                    head_o, R, fwd, qflag = compute_head_frame_world(
                        kp, body_format=bf_str,
                        keys_override=None  # or pass your custom dict once you verify indices
                    )
                    person_frames[pid] += 1

                    if head_o is not None and fwd is not None:
                        gaze_dir = fwd / (np.linalg.norm(fwd) + 1e-9)
                        fused_head_gaze[pid] = (head_o, gaze_dir)
                        person_head_sum[pid] += np.asarray(head_o, dtype=float)
                        row.extend([float(head_o[0]), float(head_o[1]), float(head_o[2]),
                                    float(gaze_dir[0]), float(gaze_dir[1]), float(gaze_dir[2])])
                    else:
                        row.extend([float("nan")] * 6)

                    # Arm joint angles from THIS body's fused 3D keypoints.
                    if ARM_ANGLES_ENABLED:
                        conf = getattr(b, "keypoint_confidence", None)
                        angles = compute_arm_angles(
                            kp, body_format=bf_str, confidences=conf,
                            conf_threshold=ARM_CONF_THRESHOLD, indices=arm_idx,
                        )
                        if arm_smoother is not None:
                            angles = arm_smoother.update(pid, angles)
                        row.extend(angles[c] for c in arm_cols)

                    writer.writerow(row)

            # Head crops: save an upper-body/"head-ish" crop per local detection.
            # Uses each camera's own 2D bodies; runs independently of demo videos.
            if SAVE_HEAD_CROPS:
                for i, frame in enumerate(frames_bgra):
                    if frame is None:
                        continue
                    for body in local_bodies[i].body_list:
                        crop = extract_head_crop(frame, body, crop_size=CROP_SIZE)
                        if crop is None:
                            continue
                        crop_path = os.path.join(
                            head_crop_dir, f"cam{i+1}_pid{body.id}_{frame_idx:06d}.png"
                        )
                        cv2.imwrite(crop_path, crop)

            # Videos: draw local 2D skeletons & (optional) gaze arrows, then write
            GAZE_DRAW_LEN_M = 2.0  # on-image arrow length (in meters along the 3D ray)
            # ======================
            #  Inside the main playback loop
            # ======================
            if WRITE_DEMO_VIDEOS:
                for i, frame in enumerate(frames_bgra):
                    if frame is None:
                        continue

                    bodies = local_bodies[i]

                    # 1️⃣ Identify which camera we're drawing to
                    cam_serial = serials[i]
                    K   = K_map[cam_serial]   # intrinsics
                    Tcw = Tcw_map[cam_serial] # extrinsics (cam_T_world)

                    # 2️⃣ Draw each local body + (optionally) gaze arrow
                    for bi, body in enumerate(bodies.body_list):
                        # Draw the local 2D skeleton first
                        frame = draw_2d_skeleton(frame, body, color=(0,255,0))

                        # Match this local body to a fused body (by id)
                        fused_id = body.id
                        if fused_id in fused_head_gaze:
                            # Get world-space head position and gaze vector
                            head_w, gaze_w = fused_head_gaze[fused_id]

                            # Project world head position into this camera's image
                            p0 = project_point(K, Tcw, head_w)
                            if p0 is None:
                                continue
                            (u0, v0, z0) = p0

                            # Project a second point along the gaze ray in world space
                            head_w2 = head_w + gaze_w * GAZE_DRAW_LEN_M
                            p1 = project_point(K, Tcw, head_w2)
                            if p1 is None:
                                continue
                            (u1, v1, z1) = p1

                            # Draw a red arrow from head → gaze direction in the image
                            pt0 = (int(round(u0)), int(round(v0)))
                            pt1 = (int(round(u1)), int(round(v1)))
                            cv2.arrowedLine(frame, pt0, pt1, (0,0,255), 2, tipLength=0.2)

                    # 3️⃣ Optionally scale and write frame to video
                    # Ensure BGRA -> BGR uint8 and size matches
                    frame_bgr = frame[:, :, :3].copy()
                    if VIDEO_SCALE != 1.0:
                        ow, oh = out_sizes[i]   # this camera's own output size
                        frame_bgr = cv2.resize(frame_bgr, (ow, oh), interpolation=cv2.INTER_LINEAR)

                    if writers[i] is not None and writers[i].isOpened():
                        writers[i].write(frame_bgr)
                    else:
                        # fall back: save a few debug PNGs so you can see what we’re producing
                        if frame_idx < 5:
                            dbg = os.path.join(video_dir, f"dbg_cam{i+1}_{frame_idx:04d}.png")
                            cv2.imwrite(dbg, frame_bgr)
                            print(f"[VIDEO][cam{i+1}] Writer not open; wrote debug {dbg}")
            frame_idx += 1

            # loop ends when both SVOs hit EOF
    finally:
        # close video writers
        for i, w in enumerate(writers):
            if w is not None:
                w.release()
                print(f"[VIDEO][cam{i+1}] writer released")
        # stop/purge clients
        for cam in clients:
            try:
                cam.stop_publishing()
                cam.disable_body_tracking()
                cam.close()
            except Exception:
                pass
        # fusion
        try:
            fusion.disable_body_tracking()
            fusion.close()
        except Exception:
            pass
        csvf.flush(); csvf.close()
        _report_person_summary(person_frames, person_head_sum, frame_idx)
        print(f"[OK] CSV written to {out_csv}")
        if ARM_ANGLES_ENABLED:
            print(f"[OK] Arm joint angles appended ({len(arm_cols)} columns)")
        if WRITE_DEMO_VIDEOS:
            print(f"[OK] Videos in {video_dir}")
        if SAVE_HEAD_CROPS:
            print(f"[OK] Head crops in {head_crop_dir}")
    return 0

def main():
    # Single-run entry point using the USER CONFIG paths above. For a whole
    # dataset of sessions, use batch_process_sessions.py instead, which
    # calls process_session() once per cam1/cam2 pair it finds.
    return process_session(SVO_FILES, FUSION_CONF, OUT_CSV, HEAD_CROP_DIR, VIDEO_DIR)

if __name__ == "__main__":
    sys.exit(main())