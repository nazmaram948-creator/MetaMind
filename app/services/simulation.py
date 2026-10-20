import random
from collections.abc import Sequence

from ..config import settings
from .repository import Role


def simulate_role_robustness(
    roles: Sequence[Role],
    skill_ids: set[str],
    *,
    seed: int = 20261020,
) -> dict[str, dict[str, object]]:
    """Estimate top-five frequency by perturbing each role's skill momentum."""
    rng = random.Random(seed)
    counts = {role.role_id: 0 for role in roles}
    runs = settings.simulation_runs
    variation = settings.simulation_variation

    for _ in range(runs):
        scored: list[tuple[float, str]] = []
        for role in roles:
            matched = len(skill_ids.intersection(role.skill_ids)) / len(role.skill_ids)
            momentum = sum(
                role.trend * (1 + rng.uniform(-variation, variation))
                for _skill_id in role.skill_ids
            ) / len(role.skill_ids)
            scored.append((matched * 0.65 + momentum * 0.35, role.role_id))
        scored.sort(reverse=True)
        for _, role_id in scored[:5]:
            counts[role_id] += 1

    return {
        role_id: {
            "runs": runs,
            "variation": variation,
            "top5_count": count,
            "top5_frequency": round(count / runs, 4),
            "label": "Estimate",
            "assumption_note": settings.assumption_note,
        }
        for role_id, count in counts.items()
    }
