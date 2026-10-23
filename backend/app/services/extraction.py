import re

from .curated_data import load_courses
from .repository import SKILLS, Skill


PII_PATTERNS = (
    re.compile(r"\b(?:age|gender|date of birth|dob)\s*[:=]?\s*[\w/-]+", re.I),
)

ESCO_SKILL_IDS = frozenset(
    skill_id
    for course in load_courses()
    for skill_id in course.skill_ids
)


# Aliases are deliberately limited to the curated ESCO IDs. Unknown phrases
# remain unmatched instead of producing invented identifiers.
SKILL_ALIASES: dict[str, str] = {
    "data entry": "ESCO-DA-01",
    "basic excel": "ESCO-EX-01",
    "excel": "ESCO-EX-01",
    "scheduling": "ESCO-PM-01",
    "customer service": "ESCO-CS-01",
    "invoicing": "ESCO-FIN-01",
    "bookkeeping": "ESCO-FIN-02",
    "administrative": "ESCO-BM-01",
    "python": "ESCO-PY-01",
    "basic sql": "ESCO-DA-02",
    "sql": "ESCO-DA-02",
    "communication": "ESCO-AI-03",
    "teamwork": "ESCO-AG-01",
    "research": "ESCO-DA-03",
    "data analysis": "ESCO-DA-01",
    "sustainability": "ESCO-SUS-01",
    "team leadership": "ESCO-PM-01",
    "inventory management": "ESCO-BM-01",
    "sales": "ESCO-BM-01",
    "conflict resolution": "ESCO-HR-01",
    "digital marketing": "ESCO-DM-01",
    "social media": "ESCO-DM-01",
    "copywriting": "ESCO-DM-02",
    "basic seo": "ESCO-DM-02",
    "call handling": "ESCO-CS-01",
    "crm software": "ESCO-CS-01",
    "empathy": "ESCO-HR-01",
    "troubleshooting": "ESCO-IT-01",
    "supply chain tracking": "ESCO-DE-01",
    "vendor management": "ESCO-BM-01",
    "process mapping": "ESCO-PM-01",
    "report generation": "ESCO-DA-03",
    "time management": "ESCO-AG-01",
    "lead generation": "ESCO-DM-01",
    "negotiation": "ESCO-BM-01",
    "b2b sales": "ESCO-BM-01",
}


def _skill_for_id(skill_id: str, phrase: str) -> Skill:
    existing = next((skill for skill in SKILLS if skill.skill_id == skill_id), None)
    return existing or Skill(skill_id, phrase.title())


def normalize_skill_phrases(phrases: list[str] | tuple[str, ...]) -> list[tuple[Skill, str, float]]:
    matches: list[tuple[Skill, str, float]] = []
    seen: set[str] = set()
    for phrase in phrases:
        normalized = phrase.strip().casefold()
        skill_id = SKILL_ALIASES.get(normalized)
        if skill_id and skill_id in ESCO_SKILL_IDS and skill_id not in seen:
            matches.append((_skill_for_id(skill_id, phrase), phrase, 0.99))
            seen.add(skill_id)
    return matches


def extract_skills(text: str) -> list[tuple[Skill, str, float]]:
    """Map case-insensitive aliases in text to verified curated ESCO IDs."""
    cleaned = text
    for pattern in PII_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    lowered = cleaned.lower()
    phrases = [
        phrase for phrase in SKILL_ALIASES
        if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered)
    ]
    return normalize_skill_phrases(phrases)
