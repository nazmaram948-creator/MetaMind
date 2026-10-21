import logging
from collections.abc import Iterable

from .repository import verified_course_ids, verified_role_ids, verified_skill_ids

logger = logging.getLogger(__name__)


def validate_db_ids(
    ids: Iterable[str], *, kind: str
) -> list[str]:
    """Return only IDs present in the verified development repository."""
    allowed_by_kind = {
        "skill": verified_skill_ids,
        "role": verified_role_ids,
        "course": verified_course_ids,
    }
    if kind not in allowed_by_kind:
        raise ValueError(f"Unsupported ID kind: {kind}")
    allowed = allowed_by_kind[kind]()
    valid: list[str] = []
    for value in ids:
        if value in allowed:
            valid.append(value)
        else:
            logger.warning("Blocked unverified %s ID: %s", kind, value)
    return valid
