"""validate_ids: every ID in a response must exist in the database.

Walks a JSON-like payload. Unknown IDs inside lists are removed; an object whose
own ID field is unknown is removed from its parent list; every drop is logged.
"""
from __future__ import annotations

import logging
from typing import Any

from .store import Store

log = logging.getLogger("skillshift.guardrail")

LIST_KEYS = {"skill_ids": "skill", "matched_skills": "skill", "missing_skills": "skill",
             "esco_skill_uris": "skill"}
SCALAR_KEYS = {"skill_id": "skill", "skill_uri": "skill", "role_id": "occupation",
               "occ_id": "occupation", "occupation_id": "occupation",
               "current_occupation_id": "occupation", "current_occ_id": "occupation",
               "course_id": "course", "snapshot_id": "snapshot", "active_snapshot_id": "snapshot",
               "baseline_snapshot_id": "snapshot", "new_snapshot_id": "snapshot", "task_id": "task"}


def known(store: Store) -> dict[str, set[str]]:
    return {"skill": store.skill_ids, "occupation": store.occupation_ids,
            "course": store.course_ids, "snapshot": set(store.snapshots),
            "task": {str(t) for t in store["tasks"].task_id} | set(store["tasks"].task_id.astype(int))}


def validate_ids(payload: Any, store: Store) -> tuple[Any, list[tuple[str, str]]]:
    """Return (clean payload, [(kind, dropped id), ...])."""
    ids = known(store)
    dropped: list[tuple[str, str]] = []

    def bad_scalar(obj: dict) -> bool:
        for key, kind in SCALAR_KEYS.items():
            v = obj.get(key)
            if v is not None and v not in ids[kind]:
                dropped.append((kind, str(v)))
                return True
        return False

    def walk(x: Any) -> Any:
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                if k in LIST_KEYS and isinstance(v, list):
                    kind = LIST_KEYS[k]
                    keep = [i for i in v if i in ids[kind]]
                    dropped.extend((kind, str(i)) for i in v if i not in ids[kind])
                    out[k] = keep
                else:
                    out[k] = walk(v)
            return out
        if isinstance(x, list):
            return [walk(i) for i in x if not (isinstance(i, dict) and bad_scalar(i))]
        return x

    if isinstance(payload, dict) and bad_scalar(payload):
        # a top-level object with an unknown own ID: blank the offending fields
        payload = {k: (None if k in SCALAR_KEYS and payload[k] not in ids[SCALAR_KEYS[k]] else v)
                   for k, v in payload.items()}
    clean = walk(payload)
    for kind, value in dropped:
        log.warning("guardrail dropped unknown %s id: %s", kind, value)
    return clean, dropped
