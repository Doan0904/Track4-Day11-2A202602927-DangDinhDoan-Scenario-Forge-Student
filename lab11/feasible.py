"""Part B: physics check. TODO 3."""
from __future__ import annotations

import math

G = 9.81


def is_feasible(p: dict) -> bool:
    """TODO 3. False for scenarios no real road user could produce. Reject if ANY of:

    - the lane change needs more sideways grip than the road has: the cosine lane change of 3.5 m over
      p["cutDur"] seconds peaks at a_lat = (pi / cutDur)^2 * 3.5 / 2; reject if a_lat > mu * g;
    - the post-merge braking p["cutBrake"] exceeds mu * g;
    - the pedestrian runs: p["pedV"] > 2.5 m/s;
    - the cut-in speed p["cutV"] is not in (0, 22] m/s.
    mu is p["mu"]. A search that keeps infeasible scenarios reports failures that cannot happen.
    """
    mu = p["mu"]
    cutDur = p["cutDur"]
    cutBrake = p["cutBrake"]
    pedV = p["pedV"]
    cutV = p["cutV"]

    # A zero duration has no finite acceleration; NaNs must not pass comparisons.
    if cutDur <= 0 or not all(math.isfinite(v) for v in (mu, cutDur, cutBrake, pedV, cutV)):
        return False

    # 1. Lane change lateral acceleration
    a_lat = (math.pi / cutDur) ** 2 * 3.5 / 2
    if a_lat > mu * G:
        return False

    # 2. Post-merge braking exceeds friction limit
    if cutBrake > mu * G:
        return False

    # 3. Pedestrian running too fast
    if pedV > 2.5:
        return False

    # 4. Cut-in speed out of range
    if cutV <= 0 or cutV > 22:
        return False

    return True
