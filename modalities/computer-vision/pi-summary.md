# What the CV setup can measure — PI summary

> **Status:** drafted
> **Owner:** unassigned
> **Last reviewed:** 2026-07-13
> **Audience:** PI / non-implementation reader
> **Use case:** single trainee performing a procedural skill; focus on arm
> kinematics & ergonomics; feasibility.

## The one-paragraph version

We put **two depth cameras** in the room and record a trainee performing a
procedural task. Nothing is attached to the trainee — no markers, no wearables
(*markerless, unobtrusive*). Offline, the two views are fused into a single
**3D skeleton** of the person, tracked frame by frame. From that skeleton we
compute **3D arm joint angles** (elbow and shoulder) and full **joint
kinematics** (position, velocity, acceleration) for the whole session. This is
the same class of measurement usually done with marker-based motion capture or
manual goniometry, but obtained passively from cameras.

## What we record

| Output | What it is |
|--------|-----------|
| `.svo2` (one per camera) | Raw stereo + depth video from each ZED camera. |
| `fusion_calibration.json` | The cameras' relative geometry (from a one-time calibration). |

## What we can produce from it

| Output | Contents | Re-identifiable? |
|--------|----------|------------------|
| **`fused_bodies.csv`** | Per-frame 3D skeleton: every joint's position (m), velocity (m/s), acceleration (m/s²), head position + gaze-direction proxy, **and arm joint angles** (below). | No (coordinates only) |
| `demo_camN.avi` | Video with the tracked skeleton drawn on it, for visual review. | **Yes** (contains video of the subject) |
| `head_crops/` | Cropped head images per frame (for an optional gaze model). | **Yes** |

### Arm joint angles (the headline metric)

Computed per frame, for **both arms**, in degrees:

| Angle | Meaning |
|-------|---------|
| **Elbow flexion** | How bent the elbow is (0° straight → ~150° fully bent). |
| **Shoulder elevation** | How far the arm is raised from hanging down (0° down, 90° horizontal, 180° overhead). |
| **Shoulder plane of elevation** | *Which direction* the arm is raised (forward vs out-to-the-side vs back). |
| **Shoulder flexion / abduction** | Classic clinical planar angles, for familiarity/comparison. |
| Segment lengths + quality flag | Per-frame data-quality signals. |

The shoulder is described with **elevation + plane-of-elevation**, an approach
recommended for 3D shoulder motion (ISB convention) because it stays stable in
positions where naïve flexion/abduction angles break down.

## Metrics we can compute for analysis

From the per-frame angle and kinematic streams, standard derived measures:

| Metric | What it tells you |
|--------|-------------------|
| **Range of motion (ROM)** | Min / max / range of each joint angle over the task — how much the trainee's shoulders and elbows moved. |
| **Ergonomic exposure** | % of time in at-risk postures (e.g. shoulder elevation > 60° / > 90°). These angles are exactly the inputs used by ergonomic scoring systems (RULA/REBA) for upper-limb strain. |
| **Movement smoothness** | Angular velocity/acceleration and jerk of the joints — smoother, more economical motion is a known marker of skill. |
| **Bimanual symmetry** | Left-vs-right comparison — how evenly the trainee uses both arms. |
| **Working envelope / reach** | 3D volume the hands sweep; hand-path length as a movement-economy measure. |
| **Task tempo** | Active vs. idle time, repetition/cycle counts, total task duration. |

These support research questions like *does arm-motion economy improve with
training?*, *how much time is spent in high-strain shoulder postures?*, and
*novice vs. expert movement differences* — without instrumenting the trainee.

## Feasibility evidence (for the "can we even do this" question)

- **End-to-end pipeline runs** from two SVO recordings to a fused 3D skeleton
  with per-joint kinematics and arm angles.
- **Angle math is validated**: a built-in self-test reproduces known
  ground-truth angles for reference poses (elbow 0°/90°, shoulder elevation with
  forward vs. sideways plane), and flags missing/low-quality joints instead of
  fabricating numbers.
- **Built-in quality signals**: per-frame tracking confidence, per-arm quality
  flags, and stable segment-length checks let us report *what fraction of the
  session was cleanly tracked* — a concrete feasibility number to show.

## Honest limitations / dependencies

- **Accuracy inherits camera calibration.** A good `fusion_calibration.json` is
  essential; a bumped camera invalidates it. We include a start-of-session
  "arms-down" calibration frame to sanity-check angles against a known 0°.
- **Occlusion** still degrades tracking when both cameras lose a hand (e.g.
  hands deep inside a task trainer). Two-camera fusion reduces this but doesn't
  eliminate it.
- **"Gaze" here is a head-orientation proxy**, not true eye-tracking. For real
  gaze, see the [eye-tracking modality](../eye-tracking/README.md).
- **Not a validated clinical goniometer (yet).** For a strong feasibility story
  we'd next do a small **concurrent-validity check** against a reference (e.g.
  a few poses measured with a goniometer or marker-based system) to quantify
  angle error.

## Suggested next step to strengthen the pitch

Run one pilot session end-to-end, then show the PI: (1) an annotated demo clip,
(2) an elbow/shoulder-angle-vs-time plot for a representative task, (3) a ROM +
ergonomic-exposure summary table, and (4) the tracking-coverage % as the
feasibility headline.

---

*Implementation details: [session-protocol.md](session-protocol.md) (runbook),
[data-spec.md](data-spec.md) (exact columns),
[code/README.md](code/README.md) (source).*
