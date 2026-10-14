"""Part A: read a rollout. TODO 1, 2 and 9 live here; the helpers below them are given."""
from __future__ import annotations

import numpy as np

from avsim import core

G = 9.81
HALF_EGO = core.CAR[0] / 2   # 2.3 m: half the ego's length


def ego_events(R: core.Rollout, k: int) -> list[dict]:
    """Failure events involving the ego in scenario k, earliest first (given).

    event["kind"] is "contact" (the boxes touched) or "block" (the ego's body stopped the pedestrian P1 on the
    crosswalk: pedestrians never walk into a car, so this is how a planner that stops too late fails them)."""
    return [e for e in R.events[k] if e["a"] == "ego" or e["b"] == "ego"]


def min_ttc(R: core.Rollout, cap: float = 10.0) -> np.ndarray:
    """TODO 1. (K,) smallest time-to-collision between the ego and whatever it is following, capped at `cap` s."""
    K, NF, N, _ = R.F.shape
    ego_idx = core.IX["ego"]

    # Check if any scenario has a crash -> TTC = 0
    has_crash = np.array([bool(ego_events(R, k)) for k in range(K)])

    # Ego state across all frames: (K, NF, 7)
    ego = R.F[:, :, ego_idx, :]
    # Leader index per frame: (K, NF)
    leader_idx = R.EGO[:, :, 3].astype(int)  # -1 = no leader

    has_leader = leader_idx >= 0

    # Clamp leader indices to valid range for gathering (we'll mask invalid ones)
    safe_idx = np.clip(leader_idx, 0, N - 1)

    # Gather leader positions and speeds: (K, NF)
    # Use advanced indexing
    k_range = np.arange(K)[:, None]
    f_range = np.arange(NF)[None, :]
    leader_data = R.F[k_range, f_range, safe_idx, :]  # (K, NF, 7)

    # Relative position in ego frame
    rx = leader_data[:, :, 0] - ego[:, :, 0]
    rz = leader_data[:, :, 1] - ego[:, :, 1]
    hx = ego[:, :, 2]
    hz = ego[:, :, 3]
    lon = rx * hx + rz * hz

    # Leader length: use core.LEN for vehicles, 0.3 for pedestrians (half-length)
    # core.LEN is (N,) array of full lengths
    actors = R.actors or core.ACTORS
    lengths = np.array([a.dims[0] for a in actors])
    pedestrians = np.array([a.kind == "ped" for a in actors])
    leader_half_len = lengths[safe_idx] / 2.0
    # For pedestrians, half-length is 0.3
    is_ped = pedestrians[safe_idx]
    leader_half_len = np.where(is_ped, 0.3, leader_half_len)

    # Gap = lon - HALF_EGO - leader_half_len, clipped at 0
    gap = np.maximum(0.0, lon - HALF_EGO - leader_half_len)

    # Speed difference
    v_ego = ego[:, :, 4]
    v_leader = leader_data[:, :, 4]
    dv = v_ego - v_leader

    # TTC only when closing in by more than 0.1 m/s
    closing = dv > 0.1
    valid = has_leader & closing

    ttc = np.where(valid, gap / np.maximum(dv, 1e-6), np.inf)
    ttc = np.minimum(cap, ttc)

    # Min over all frames
    result = ttc.min(axis=1)

    # Crashed scenarios get 0
    result = np.where(has_crash, 0.0, result)

    return result


def contact_type(R: core.Rollout, k: int, event: dict) -> str:
    """TODO 2. 'front' (the ego ran into it), 'rear' (it ran into the ego) or 'side', at the contact frame."""
    f = event["f"]
    ego_idx = core.IX["ego"]
    # Determine the other actor
    other_id = event["b"] if event["a"] == "ego" else event["a"]
    other_idx = R.ids.index(other_id)

    ex, ez = R.F[k, f, ego_idx, 0], R.F[k, f, ego_idx, 1]
    ehx, ehz = R.F[k, f, ego_idx, 2], R.F[k, f, ego_idx, 3]
    ox, oz = R.F[k, f, other_idx, 0], R.F[k, f, other_idx, 1]

    # Put other actor in ego's frame
    rx = ox - ex
    rz = oz - ez
    lon = rx * ehx + rz * ehz
    lat = -rx * ehz + rz * ehx

    if lon > 2.3 and abs(lat) < 1.6:
        return "front"
    elif lon < -2.3 and abs(lat) < 1.6:
        return "rear"
    else:
        return "side"


def progress_metrics(R: core.Rollout) -> tuple[np.ndarray, np.ndarray]:
    """TODO 9. Two (K,) arrays: the distance the ego covers in the 24 s (sum of frame-to-frame steps, metres),
    and the number of frames where the ego brakes harder than 3 m/s^2 (acceleration column < -3)."""
    ego_idx = core.IX["ego"]
    ego = R.F[:, :, ego_idx, :]  # (K, NF, 7)

    # Distance: sum of frame-to-frame displacements
    dx = np.diff(ego[:, :, 0], axis=1)
    dz = np.diff(ego[:, :, 1], axis=1)
    dist = np.sum(np.hypot(dx, dz), axis=1)

    # Harsh braking: frames where acceleration < -3
    acc = ego[:, :, 5]  # (K, NF)
    harsh = np.sum(acc < -3.0, axis=1)

    return dist, harsh


# ---------------------------------------------------------------- given helpers

def pair_min_ttc(R, follower, leader, cap=10.0, lat_max=2.2, leader_vmin=-1.0):
    """(K,) smallest TTC of `follower` running into `leader` while they share a corridor."""
    F = R.F
    a, b = F[:, :, core.IX[follower]], F[:, :, core.IX[leader]]
    rx, rz = b[..., 0] - a[..., 0], b[..., 1] - a[..., 1]
    lon = rx * a[..., 2] + rz * a[..., 3]
    lat = -rx * a[..., 3] + rz * a[..., 2]
    gap = np.maximum(lon - core.LEN[core.IX[follower]] / 2 - core.LEN[core.IX[leader]] / 2, 0.0)
    dv = a[..., 4] - b[..., 4]
    ok = (lon > 0) & (np.abs(lat) < lat_max) & (dv > 0.1) & (b[..., 4] >= leader_vmin)
    ttc = np.where(ok, gap / np.maximum(dv, 1e-6), np.inf)
    return np.minimum(cap, ttc.min(1))


def ped_room(R, cap=30.0):
    """(K,) smallest stopping room [m] left while the crossing pedestrian is in the ego's lane
    (distance to them minus the ego's braking distance at mu*g). Negative = could not have stopped."""
    e, p = R.F[:, :, core.IX["ego"]], R.F[:, :, core.IX["P1"]]
    mu = np.asarray(R.params["mu"])[:, None]
    inlane = np.abs(p[..., 1] - e[..., 1]) < 1.9
    ahead = p[..., 0] - e[..., 0] - HALF_EGO
    room = np.where(inlane & (ahead > -1.0), ahead - e[..., 4] ** 2 / (2 * mu * G), cap)
    return np.clip(room.min(1), -cap, cap)
