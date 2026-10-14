"""Part E: choose a policy honestly. TODO 10."""
from __future__ import annotations


def choose_policy(table: list[dict], baseline_progress: float, max_loss: float = 0.05):
    """TODO 10. table rows: dict(policy=..., fail_hi=upper 95% bound of the failure rate on the TRAIN sample,
    progress=mean distance on the natural progress sample). Return the row with the lowest fail_hi among rows that
    keep at least (1 - max_loss) of the baseline's progress; break ties by higher progress. None if no row qualifies.

    Ranking by the UPPER bound, not the point estimate, stops you picking a policy that only looks safe
    because its few test crashes happened not to be drawn."""
    min_progress = (1 - max_loss) * baseline_progress

    # Filter rows that keep enough progress
    qualified = [row for row in table if row["progress"] >= min_progress]

    if not qualified:
        return None

    # Sort by fail_hi ascending, then by progress descending (for tie-breaking)
    qualified.sort(key=lambda r: (r["fail_hi"], -r["progress"]))

    return qualified[0]
