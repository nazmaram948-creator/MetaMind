import re

from .repository import SKILLS, Skill


PII_PATTERNS = (
    re.compile(r"\b(?:age|gender|date of birth|dob)\s*[:=]?\s*[\w/-]+", re.I),
)


def extract_skills(text: str) -> list[tuple[Skill, str, float]]:
    """Deterministically map known phrases; unknown or injected IDs are ignored."""
    cleaned = text
    for pattern in PII_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    lowered = cleaned.lower()
    matches: list[tuple[Skill, str, float]] = []
    phrases = {
        "skill-data-analysis": ("data analysis", "data analyst", "analytics"),
        "skill-spreadsheets": ("spreadsheet", "excel"),
        "skill-customer-service": ("customer service", "client support"),
        "skill-project-management": ("project management", "project planning"),
        "skill-digital-marketing": ("digital marketing", "social media"),
        "skill-sustainability-reporting": ("sustainability reporting", "esg reporting"),
    }
    for skill in SKILLS:
        phrase = next((candidate for candidate in phrases[skill.skill_id] if candidate in lowered), None)
        if phrase:
            matches.append((skill, phrase, 0.95))
    return matches
