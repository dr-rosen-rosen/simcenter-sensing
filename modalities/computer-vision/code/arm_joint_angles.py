#!/usr/bin/env python3
"""
arm_joint_angles.py
===================

Compute upper-limb (arm) joint angles from 3D body keypoints produced by the
ZED Fusion pipeline (the "hybridized" fused skeleton in WORLD coordinates).

This module is deliberately decoupled from the ZED SDK for its math so it can
run in two ways:

  1) In-pipeline: import `compute_arm_angles` from `replay_fusion_enhanced.py`
     and append angle columns to each fused-body CSV row as it is written.
  2) Offline: run this file on an already-produced `fused_bodies.csv` to add
     angle columns (see `annotate_csv` / the CLI at the bottom).

Angle conventions
-----------------
All angles are in DEGREES. We build a subject-anchored anatomical frame from
the shoulders and hips, so results are invariant to the world coordinate
convention (e.g. RIGHT_HANDED_Z_UP vs. anything else):

    e_sup   : superior (up)      = mid_shoulder - mid_hip
    e_right : subject's right    = right_shoulder - left_shoulder (orthogonalized)
    e_ant   : anterior (forward) = e_sup x e_right  (right-handed anatomy)

Reported per arm (prefix "L_"/"R_"):

  elbow_flexion_deg
      Clinical elbow flexion. 0 deg = fully extended (straight arm),
      increasing as the elbow bends. = 180 - (included segment angle).
  elbow_included_deg
      Raw included angle between upper-arm and forearm segments (0..180),
      provided for transparency/debugging.
  shoulder_elevation_deg
      How far the humerus is raised away from the resting-down direction.
      0 deg = arm hanging down, 90 deg = arm horizontal, 180 deg = straight up.
      This is the robust, gimbal-free "elevation angle" (ISB-style).
  shoulder_plane_deg
      Plane of elevation (azimuth of the raised arm), side-symmetric:
      0 deg = pure forward flexion, +90 deg = pure lateral abduction,
      +/-180 deg = extension (backward), negative = across-body / adduction side.
  shoulder_flexion_deg
      Classic clinical sagittal-plane angle (forward +, backward -). Convenient
      but degenerate when the arm is abducted; prefer elevation+plane for
      combined motions.
  shoulder_abduction_deg
      Classic clinical coronal-plane angle (out-to-side +, across-body -).
  upperarm_len_m, forearm_len_m
      Segment lengths (meters), useful QA signals; wildly varying lengths flag
      bad tracking.
  quality
      One of: "ok", "low_confidence", "missing_joints", "degenerate_trunk",
      "degenerate_segment". Angles that could not be computed are NaN.

References (conventions inspired by, not a verbatim implementation of):
  Wu et al., "ISB recommendation on definitions of joint coordinate systems...
  Part II: shoulder, elbow, wrist and hand," J. Biomech. 38 (2005) 981-992.
"""

from __future__ import annotations

import csv
import math
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Keypoint index resolution
# ---------------------------------------------------------------------------
# Official Stereolabs keypoint orderings. These are the fallback used when the
# ZED SDK enums are not importable (e.g. offline CSV post-processing on a
# machine without pyzed). When pyzed IS available we resolve indices from the
# SDK enum instead, so the module tracks the SDK even if these ever change.
#
# NOTE: gaze_geometry.py carries a *different*, self-described "verify once"
# index set for head/eye points; do NOT copy arm indices from there. The values
# below follow the documented BODY_34 / BODY_38 layouts.
_FALLBACK_BODY34 = {
    "left_shoulder": 5,  "left_elbow": 6,  "left_wrist": 7,
    "right_shoulder": 12, "right_elbow": 13, "right_wrist": 14,
    "left_hip": 18, "right_hip": 22,
    "pelvis": 0, "neck": 3,
}
_FALLBACK_BODY38 = {
    "left_shoulder": 12, "left_elbow": 14, "left_wrist": 16,
    "right_shoulder": 13, "right_elbow": 15, "right_wrist": 17,
    "left_hip": 18, "right_hip": 19,
    "pelvis": 0, "neck": 4,
}

# Names to pull from the SDK enum when available.
_ENUM_NAMES = {
    "left_shoulder": "LEFT_SHOULDER", "left_elbow": "LEFT_ELBOW", "left_wrist": "LEFT_WRIST",
    "right_shoulder": "RIGHT_SHOULDER", "right_elbow": "RIGHT_ELBOW", "right_wrist": "RIGHT_WRIST",
    "left_hip": "LEFT_HIP", "right_hip": "RIGHT_HIP",
    "pelvis": "PELVIS", "neck": "NECK",
}


def get_arm_indices(body_format: str = "BODY_34") -> Dict[str, int]:
    """
    Return a dict mapping semantic joint names to keypoint indices for the given
    body format ("BODY_34" or "BODY_38").

    Prefers the live ZED SDK enum (sl.BODY_34_PARTS / sl.BODY_38_PARTS) so the
    mapping stays correct across SDK versions; falls back to documented
    constants when pyzed is unavailable.
    """
    bf = body_format.upper()
    if bf not in ("BODY_34", "BODY_38"):
        raise ValueError(f"Unsupported body_format: {body_format!r}")

    # Try the SDK enum first.
    try:
        import pyzed.sl as sl  # noqa: WPS433 (optional dependency)
        enum = sl.BODY_34_PARTS if bf == "BODY_34" else sl.BODY_38_PARTS
        idx = {}
        for key, enum_name in _ENUM_NAMES.items():
            member = getattr(enum, enum_name, None)
            if member is None:
                raise AttributeError(enum_name)
            idx[key] = int(member.value)
        return idx
    except Exception:
        # Offline / SDK missing / enum member renamed -> documented fallback.
        return dict(_FALLBACK_BODY34 if bf == "BODY_34" else _FALLBACK_BODY38)


# ---------------------------------------------------------------------------
# Small vector helpers (epsilon-guarded)
# ---------------------------------------------------------------------------
_EPS = 1e-9


def _finite_point(p: Optional[Sequence[float]]) -> Optional[np.ndarray]:
    """Return p as a float (3,) array, or None if missing/non-finite."""
    if p is None:
        return None
    a = np.asarray(p, dtype=float).reshape(-1)[:3]
    if a.shape[0] < 3 or not np.all(np.isfinite(a)):
        return None
    return a


def _unit(v: np.ndarray) -> Optional[np.ndarray]:
    n = float(np.linalg.norm(v))
    if n < _EPS:
        return None
    return v / n


def _reject(v: np.ndarray, axis_unit: np.ndarray) -> np.ndarray:
    """Component of v perpendicular to a UNIT axis."""
    return v - float(np.dot(v, axis_unit)) * axis_unit


def _angle_between(a: np.ndarray, b: np.ndarray) -> float:
    """Unsigned angle (deg, 0..180) between two vectors, NaN if either is ~0."""
    ua, ub = _unit(a), _unit(b)
    if ua is None or ub is None:
        return float("nan")
    c = float(np.clip(np.dot(ua, ub), -1.0, 1.0))
    return math.degrees(math.acos(c))


# ---------------------------------------------------------------------------
# Anatomical trunk frame
# ---------------------------------------------------------------------------
class TrunkFrame:
    """Right-handed, subject-anchored orthonormal frame (all axes unit vectors).

    e_sup   : superior (up)
    e_right : subject's right (horizontalized w.r.t. e_sup)
    e_ant   : anterior (forward) = e_sup x e_right
    origin  : mid-shoulder point
    """

    __slots__ = ("origin", "e_sup", "e_right", "e_ant", "valid")

    def __init__(self, origin, e_sup, e_right, e_ant, valid):
        self.origin = origin
        self.e_sup = e_sup
        self.e_right = e_right
        self.e_ant = e_ant
        self.valid = valid


def build_trunk_frame(pts: Dict[str, Optional[np.ndarray]]) -> TrunkFrame:
    """Build the anatomical trunk frame from resolved landmark points.

    Requires both shoulders. Uses both hips when present (preferred); falls back
    to neck/pelvis for the superior axis if a hip is missing.
    """
    lsh, rsh = pts.get("left_shoulder"), pts.get("right_shoulder")
    if lsh is None or rsh is None:
        return TrunkFrame(None, None, None, None, False)

    mid_sh = 0.5 * (lsh + rsh)

    lhip, rhip = pts.get("left_hip"), pts.get("right_hip")
    if lhip is not None and rhip is not None:
        mid_hip = 0.5 * (lhip + rhip)
    else:
        # Fallback: use pelvis, else neck (superior axis only).
        mid_hip = pts.get("pelvis")
        if mid_hip is None:
            neck = pts.get("neck")
            # neck is above mid_shoulder; invert so e_sup still points up.
            mid_hip = (2.0 * mid_sh - neck) if neck is not None else None

    e_sup = _unit(mid_sh - mid_hip) if mid_hip is not None else None
    # subject's right: from left shoulder to right shoulder
    e_right_raw = rsh - lsh
    if e_sup is None:
        # No vertical reference: use raw shoulder axis as right, synthesize the
        # rest from any non-parallel world axis. Marked invalid for shoulder
        # angles but still lets elbow angles be computed by the caller.
        return TrunkFrame(mid_sh, None, _unit(e_right_raw), None, False)

    e_right = _unit(_reject(e_right_raw, e_sup))
    if e_right is None:
        return TrunkFrame(mid_sh, e_sup, None, None, False)

    e_ant = _unit(np.cross(e_sup, e_right))
    if e_ant is None:
        return TrunkFrame(mid_sh, e_sup, e_right, None, False)

    # Re-orthonormalize right from ant x sup to guarantee a clean right-handed set.
    e_right = _unit(np.cross(e_ant, e_sup))
    return TrunkFrame(mid_sh, e_sup, e_right, e_ant, True)


# ---------------------------------------------------------------------------
# Per-arm angle computation
# ---------------------------------------------------------------------------
# Field order used for CSV headers/rows. Kept explicit so the header and the
# row always agree.
PER_ARM_FIELDS = (
    "elbow_flexion_deg",
    "elbow_included_deg",
    "shoulder_elevation_deg",
    "shoulder_plane_deg",
    "shoulder_flexion_deg",
    "shoulder_abduction_deg",
    "upperarm_len_m",
    "forearm_len_m",
    "quality",
)
_SIDES = ("L", "R")


def csv_angle_columns() -> list:
    """Column names appended to the fused CSV, in order."""
    cols = []
    for side in _SIDES:
        for f in PER_ARM_FIELDS:
            cols.append(f"{side}_{f}")
    return cols


def _nan_arm(quality: str) -> Dict[str, float]:
    d = {f: float("nan") for f in PER_ARM_FIELDS}
    d["quality"] = quality
    return d


def _compute_one_arm(
    shoulder: Optional[np.ndarray],
    elbow: Optional[np.ndarray],
    wrist: Optional[np.ndarray],
    trunk: TrunkFrame,
    side: str,
) -> Dict[str, float]:
    """Compute one arm's angles. `side` is "L" or "R" (sets abduction sign)."""
    if shoulder is None or elbow is None or wrist is None:
        return _nan_arm("missing_joints")

    upper = shoulder - elbow      # elbow -> shoulder
    fore = wrist - elbow          # elbow -> wrist
    humerus = elbow - shoulder    # shoulder -> elbow (down the upper arm)

    upperarm_len = float(np.linalg.norm(shoulder - elbow))
    forearm_len = float(np.linalg.norm(wrist - elbow))

    out = _nan_arm("ok")
    out["upperarm_len_m"] = upperarm_len
    out["forearm_len_m"] = forearm_len

    # --- Elbow (does not need the trunk frame) ---
    included = _angle_between(upper, fore)
    if math.isnan(included):
        out["quality"] = "degenerate_segment"
    else:
        out["elbow_included_deg"] = included
        out["elbow_flexion_deg"] = 180.0 - included

    # --- Shoulder (needs a valid trunk frame) ---
    if not trunk.valid:
        # Elbow may still be valid; flag that shoulder angles are unavailable.
        if out["quality"] == "ok":
            out["quality"] = "degenerate_trunk"
        return out

    h = _unit(humerus)
    if h is None:
        if out["quality"] == "ok":
            out["quality"] = "degenerate_segment"
        return out

    e_sup, e_ant, e_right = trunk.e_sup, trunk.e_ant, trunk.e_right
    down = -e_sup
    # Lateral direction for THIS arm so abduction is positive when moving away
    # from the body on the arm's own side.
    lateral = e_right if side == "R" else -e_right

    # Elevation angle: how far the humerus is from hanging straight down.
    out["shoulder_elevation_deg"] = _angle_between(humerus, down)

    # Plane of elevation: azimuth of the humerus in the horizontal plane.
    h_horiz = _reject(humerus, e_sup)
    fwd_c = float(np.dot(h_horiz, e_ant))
    lat_c = float(np.dot(h_horiz, lateral))
    if abs(fwd_c) < _EPS and abs(lat_c) < _EPS:
        out["shoulder_plane_deg"] = 0.0  # arm ~vertical: plane is undefined -> 0
    else:
        out["shoulder_plane_deg"] = math.degrees(math.atan2(lat_c, fwd_c))

    # Classic clinical planar angles (projections). Measured from the downward
    # direction; forward/lateral positive.
    #   Sagittal plane spanned by (e_sup, e_ant): flexion.
    h_sag = _reject(humerus, e_right)     # remove medio-lateral component
    out["shoulder_flexion_deg"] = math.degrees(
        math.atan2(float(np.dot(h_sag, e_ant)), float(np.dot(h_sag, down)))
    )
    #   Coronal plane spanned by (e_sup, lateral): abduction.
    h_cor = _reject(humerus, e_ant)       # remove anterior-posterior component
    out["shoulder_abduction_deg"] = math.degrees(
        math.atan2(float(np.dot(h_cor, lateral)), float(np.dot(h_cor, down)))
    )
    return out


def compute_arm_angles(
    keypoints: Sequence[Sequence[float]],
    body_format: str = "BODY_34",
    confidences: Optional[Sequence[float]] = None,
    conf_threshold: float = 0.0,
    indices: Optional[Dict[str, int]] = None,
) -> Dict[str, float]:
    """
    Compute both arms' joint angles from a single skeleton's 3D keypoints.

    Args:
      keypoints: (K,3) array-like in WORLD meters.
      body_format: "BODY_34" or "BODY_38".
      confidences: optional (K,) per-keypoint confidence (ZED
        body.keypoint_confidence). Values may be 0..100 or 0..1; the threshold
        is compared directly, so pass conf_threshold in the same scale.
      conf_threshold: joints with confidence below this are treated as missing.
      indices: optional precomputed name->index map (see get_arm_indices); pass
        it once per run to avoid repeated SDK enum lookups.

    Returns:
      Flat dict with keys csv_angle_columns() -> float/str. Missing or
      low-confidence inputs yield NaN angles and a descriptive per-arm quality.
    """
    kp = np.asarray(keypoints, dtype=float)
    if kp.ndim != 2 or kp.shape[1] < 3:
        raise ValueError(f"keypoints must be (K,3); got shape {kp.shape}")
    K = kp.shape[0]

    idx = indices if indices is not None else get_arm_indices(body_format)
    conf = None if confidences is None else np.asarray(confidences, dtype=float).reshape(-1)

    def resolve(name: str) -> Optional[np.ndarray]:
        i = idx.get(name)
        if i is None or i < 0 or i >= K:
            return None
        if conf is not None and i < conf.shape[0] and conf[i] < conf_threshold:
            return None
        return _finite_point(kp[i])

    pts = {name: resolve(name) for name in idx}
    trunk = build_trunk_frame(pts)

    result: Dict[str, float] = {}
    for side, sh, el, wr in (
        ("L", "left_shoulder", "left_elbow", "left_wrist"),
        ("R", "right_shoulder", "right_elbow", "right_wrist"),
    ):
        arm = _compute_one_arm(pts.get(sh), pts.get(el), pts.get(wr), trunk, side)
        # If joints were dropped specifically due to confidence, refine the flag.
        if arm["quality"] == "missing_joints" and conf is not None:
            for nm in (sh, el, wr):
                i = idx.get(nm)
                if i is not None and 0 <= i < K and _finite_point(kp[i]) is not None:
                    arm["quality"] = "low_confidence"
                    break
        for f in PER_ARM_FIELDS:
            result[f"{side}_{f}"] = arm[f]
    return result


# ---------------------------------------------------------------------------
# Temporal smoothing (optional; robust to keypoint jitter/outliers)
# ---------------------------------------------------------------------------
class AngleSmoother:
    """Streaming per-(person, field) smoother.

    - Linear angle fields use a moving MEDIAN (robust to single-frame outliers).
    - The circular field `shoulder_plane_deg` uses a circular mean over the
      window (mean of unit vectors) so the +/-180 wrap is handled correctly.
    - NaNs are ignored; if the whole window is NaN the output stays NaN.

    Usage:
        sm = AngleSmoother(window=5)
        smoothed = sm.update(person_id, angle_dict)
    """

    _CIRCULAR = frozenset({"shoulder_plane_deg"})

    def __init__(self, window: int = 5):
        if window < 1:
            raise ValueError("window must be >= 1")
        self.window = window
        self._buf: Dict[Tuple[int, str], list] = {}

    def update(self, person_id: int, angles: Dict[str, float]) -> Dict[str, float]:
        out = dict(angles)
        for side in _SIDES:
            for f in PER_ARM_FIELDS:
                if f == "quality":
                    continue
                col = f"{side}_{f}"
                val = angles.get(col, float("nan"))
                key = (person_id, col)
                buf = self._buf.setdefault(key, [])
                buf.append(val)
                if len(buf) > self.window:
                    buf.pop(0)
                vals = [v for v in buf if v is not None and not math.isnan(v)]
                if not vals:
                    out[col] = float("nan")
                elif f in self._CIRCULAR:
                    ang = np.radians(vals)
                    out[col] = math.degrees(
                        math.atan2(float(np.mean(np.sin(ang))),
                                   float(np.mean(np.cos(ang))))
                    )
                else:
                    out[col] = float(np.median(vals))
        return out


# ---------------------------------------------------------------------------
# Offline CSV post-processing
# ---------------------------------------------------------------------------
def _infer_kp_count(header: Sequence[str]) -> int:
    """Count how many k{i}_x columns exist -> number of keypoints."""
    n = 0
    while f"k{n}_x" in header:
        n += 1
    return n


def annotate_csv(
    in_csv: str,
    out_csv: str,
    body_format: Optional[str] = None,
    conf_threshold: float = 0.0,
    smooth_window: int = 0,
) -> int:
    """
    Read a fused_bodies.csv (as written by replay_fusion_enhanced.py), compute
    arm angles per row from its k{i}_x/y/z keypoint columns, and write a new CSV
    with the angle columns appended.

    body_format: "BODY_34"/"BODY_38". If None, inferred from the keypoint count
      (34 or 38); other counts require an explicit body_format.
    conf_threshold: forwarded to compute_arm_angles (the fused CSV has no
      per-keypoint confidence, so this only matters if you extend the schema).
    smooth_window: if > 1, apply AngleSmoother with this window (rows are assumed
      time-ordered per person, which is how the pipeline writes them).

    Returns the number of body rows processed.
    """
    with open(in_csv, "r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        kp_count = _infer_kp_count(header)
        if body_format is None:
            if kp_count in (34, 38):
                body_format = f"BODY_{kp_count}"
            else:
                raise ValueError(
                    f"Could not infer body_format from {kp_count} keypoints; "
                    "pass body_format explicitly."
                )
        indices = get_arm_indices(body_format)

        col_index = {name: i for i, name in enumerate(header)}
        kx = [col_index[f"k{i}_x"] for i in range(kp_count)]
        ky = [col_index[f"k{i}_y"] for i in range(kp_count)]
        kz = [col_index[f"k{i}_z"] for i in range(kp_count)]
        pid_col = col_index.get("person_id")

        angle_cols = csv_angle_columns()
        smoother = AngleSmoother(smooth_window) if smooth_window and smooth_window > 1 else None

        rows_out = []
        n = 0
        for row in reader:
            if not row:
                continue
            kp = np.empty((kp_count, 3), dtype=float)
            for i in range(kp_count):
                try:
                    kp[i] = (float(row[kx[i]]), float(row[ky[i]]), float(row[kz[i]]))
                except (ValueError, IndexError):
                    kp[i] = (float("nan"), float("nan"), float("nan"))
            angles = compute_arm_angles(
                kp, body_format=body_format, conf_threshold=conf_threshold,
                indices=indices,
            )
            if smoother is not None and pid_col is not None:
                try:
                    pid = int(float(row[pid_col]))
                except (ValueError, IndexError):
                    pid = -1
                angles = smoother.update(pid, angles)
            rows_out.append(row + [_fmt(angles[c]) for c in angle_cols])
            n += 1

    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header + angle_cols)
        writer.writerows(rows_out)
    return n


def _fmt(v) -> str:
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return f"{v:.6f}"


# ---------------------------------------------------------------------------
# Self-test (synthetic poses with known ground-truth angles)
# ---------------------------------------------------------------------------
def _make_skeleton_body34(joints: Dict[str, np.ndarray]) -> np.ndarray:
    """Build a (34,3) keypoint array from a few named joints (rest NaN)."""
    idx = _FALLBACK_BODY34
    kp = np.full((34, 3), np.nan, dtype=float)
    for name, p in joints.items():
        kp[idx[name]] = p
    return kp


def _selftest() -> int:
    """Return 0 on success, non-zero on first failed assertion."""
    # World frame here: X=forward(anterior), Y=subject-left, Z=up. We construct
    # trunk landmarks consistent with that so we can predict the outputs.
    #   shoulders on the Y axis, hips below on Z.
    Lsh = np.array([0.0, 0.20, 1.40])
    Rsh = np.array([0.0, -0.20, 1.40])
    Lhip = np.array([0.0, 0.15, 0.90])
    Rhip = np.array([0.0, -0.15, 0.90])

    def check(name, got, want, tol=1.0):
        if math.isnan(got) or abs(got - want) > tol:
            print(f"[FAIL] {name}: got {got:.3f}, want {want:.3f}")
            return False
        print(f"[ok]   {name}: {got:.3f} (~{want})")
        return True

    ok = True

    # --- Pose 1: right arm hanging straight down, elbow straight ---
    r_sh = Rsh
    r_el = Rsh + np.array([0.0, 0.0, -0.30])   # straight down
    r_wr = r_el + np.array([0.0, 0.0, -0.25])  # straight down
    kp = _make_skeleton_body34(dict(
        left_shoulder=Lsh, right_shoulder=Rsh, left_hip=Lhip, right_hip=Rhip,
        right_elbow=r_el, right_wrist=r_wr,
    ))
    a = compute_arm_angles(kp, "BODY_34")
    ok &= check("P1 R_elbow_flexion", a["R_elbow_flexion_deg"], 0.0)
    ok &= check("P1 R_shoulder_elevation", a["R_shoulder_elevation_deg"], 0.0)

    # --- Pose 2: right elbow flexed 90 deg (upper arm down, forearm forward) ---
    r_el = Rsh + np.array([0.0, 0.0, -0.30])
    r_wr = r_el + np.array([0.25, 0.0, 0.0])   # forearm points forward (+X)
    kp = _make_skeleton_body34(dict(
        left_shoulder=Lsh, right_shoulder=Rsh, left_hip=Lhip, right_hip=Rhip,
        right_elbow=r_el, right_wrist=r_wr,
    ))
    a = compute_arm_angles(kp, "BODY_34")
    ok &= check("P2 R_elbow_flexion", a["R_elbow_flexion_deg"], 90.0)

    # --- Pose 3: right arm raised forward to horizontal (flexion) ---
    r_el = Rsh + np.array([0.30, 0.0, 0.0])    # straight forward (+X)
    r_wr = r_el + np.array([0.25, 0.0, 0.0])
    kp = _make_skeleton_body34(dict(
        left_shoulder=Lsh, right_shoulder=Rsh, left_hip=Lhip, right_hip=Rhip,
        right_elbow=r_el, right_wrist=r_wr,
    ))
    a = compute_arm_angles(kp, "BODY_34")
    ok &= check("P3 R_shoulder_elevation", a["R_shoulder_elevation_deg"], 90.0)
    ok &= check("P3 R_shoulder_plane(forward=0)", a["R_shoulder_plane_deg"], 0.0)
    ok &= check("P3 R_shoulder_flexion", a["R_shoulder_flexion_deg"], 90.0)

    # --- Pose 4: right arm abducted to the side, horizontal ---
    #   subject's right is -Y in this world, so raise arm along -Y.
    r_el = Rsh + np.array([0.0, -0.30, 0.0])
    r_wr = r_el + np.array([0.0, -0.25, 0.0])
    kp = _make_skeleton_body34(dict(
        left_shoulder=Lsh, right_shoulder=Rsh, left_hip=Lhip, right_hip=Rhip,
        right_elbow=r_el, right_wrist=r_wr,
    ))
    a = compute_arm_angles(kp, "BODY_34")
    ok &= check("P4 R_shoulder_elevation", a["R_shoulder_elevation_deg"], 90.0)
    ok &= check("P4 R_shoulder_plane(abduct=+90)", a["R_shoulder_plane_deg"], 90.0)
    ok &= check("P4 R_shoulder_abduction", a["R_shoulder_abduction_deg"], 90.0)

    # --- Pose 5: missing wrist -> graceful NaN + quality flag ---
    kp = _make_skeleton_body34(dict(
        left_shoulder=Lsh, right_shoulder=Rsh, left_hip=Lhip, right_hip=Rhip,
        right_elbow=r_el,
    ))
    a = compute_arm_angles(kp, "BODY_34")
    ok &= (math.isnan(a["R_elbow_flexion_deg"]) and a["R_quality"] == "missing_joints")
    print(f"[{'ok' if ok else 'FAIL'}]   P5 missing-joint handling: {a['R_quality']}")

    print("\nSELF-TEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Compute arm joint angles from a fused_bodies.csv, "
                    "or run the built-in self-test."
    )
    ap.add_argument("in_csv", nargs="?", help="input fused_bodies.csv")
    ap.add_argument("out_csv", nargs="?", help="output CSV with angle columns")
    ap.add_argument("--body-format", choices=["BODY_34", "BODY_38"], default=None,
                    help="override auto-detection")
    ap.add_argument("--smooth-window", type=int, default=0,
                    help="moving-window size for temporal smoothing (0/1 = off)")
    ap.add_argument("--selftest", action="store_true",
                    help="run synthetic self-test and exit")
    args = ap.parse_args(argv)

    if args.selftest or not args.in_csv:
        return _selftest()

    if not args.out_csv:
        print("error: out_csv is required when in_csv is given", file=__import__("sys").stderr)
        return 2

    n = annotate_csv(
        args.in_csv, args.out_csv,
        body_format=args.body_format,
        smooth_window=args.smooth_window,
    )
    print(f"[OK] wrote {args.out_csv} ({n} rows) with columns: {', '.join(csv_angle_columns())}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
