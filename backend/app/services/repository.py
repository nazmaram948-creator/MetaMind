from dataclasses import dataclass
from pathlib import Path
import csv

from .curated_data import CURATED, load_courses


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Skill:
    skill_id: str
    skill_name: str


@dataclass(frozen=True)
class Role:
    role_id: str
    role_title: str
    skill_ids: tuple[str, ...]
    trend: float


@dataclass(frozen=True)
class Course:
    course_id: str
    title: str
    provider: str
    url: str
    cost: int
    hrd_corp_claimable: bool
    sdg_tags: tuple[str, ...]
    skill_ids: tuple[str, ...]
    hours: int | None
    hours_verified: bool | None


SKILLS = (
    Skill("skill-data-analysis", "Data analysis"),
    Skill("skill-spreadsheets", "Spreadsheet software"),
    Skill("skill-customer-service", "Customer service"),
    Skill("skill-project-management", "Project management"),
    Skill("skill-digital-marketing", "Digital marketing"),
    Skill("skill-sustainability-reporting", "Sustainability reporting"),
)

ROLES = (
    Role("role-data-analyst", "Data analyst", ("skill-data-analysis", "skill-spreadsheets"), 0.90),
    Role("role-business-analyst", "Business analyst", ("skill-data-analysis", "skill-project-management"), 0.84),
    Role("role-project-support", "Project support officer", ("skill-project-management", "skill-spreadsheets"), 0.72),
    Role("role-digital-marketing", "Digital marketing manager", ("skill-digital-marketing", "skill-customer-service"), 0.78),
    Role("role-sustainability", "Sustainability manager", ("skill-sustainability-reporting", "skill-data-analysis"), 0.81),
)

COURSES = (
    Course(
        "course-spreadsheet-analysis",
        "Spreadsheet analysis foundations",
        "Development catalogue",
        "https://example.invalid/courses/spreadsheet-analysis",
        0,
        False,
        ("SDG 8: Decent Work",),
        ("skill-spreadsheets", "skill-data-analysis"),
        2.0,
        True,
    ),
    Course(
        "course-project-practice",
        "Practical project coordination",
        "Development catalogue",
        "https://example.invalid/courses/project-practice",
        0,
        False,
        ("SDG 8: Decent Work",),
        ("skill-project-management",),
        4.0,
        False,
    ),
)


def verified_skill_ids() -> set[str]:
    return {skill.skill_id for skill in SKILLS}


def verified_role_ids() -> set[str]:
    return {role.role_id for role in ROLES}


def verified_course_ids() -> set[str]:
    return {course.course_id for course in course_catalogue()}


def courses_for_skill(skill_id: str) -> list[Course]:
    prefixes = {
        "skill-data-analysis": ("ESCO-DA-",),
        "skill-spreadsheets": ("ESCO-EX-",),
        "skill-customer-service": ("ESCO-CS-",),
        "skill-project-management": ("ESCO-PM-", "ESCO-AG-"),
        "skill-digital-marketing": ("ESCO-DM-",),
        "skill-sustainability-reporting": ("ESCO-ESG-", "ESCO-SUS-"),
    }
    accepted = prefixes.get(skill_id, ())
    return [
        course for course in course_catalogue()
        if skill_id in course.skill_ids
        or any(course_skill.startswith(prefix) for course_skill in course.skill_ids for prefix in accepted)
    ]


def course_catalogue() -> tuple[Course, ...]:
    """Load the curated catalogue when available, otherwise use dev fixtures."""
    path = CURATED / "courses.csv"
    if not path.exists():
        return COURSES
    return tuple(
        Course(
            course_id=course.course_id,
            title=course.course_title,
            provider=course.provider,
            url=course.url,
            cost=course.cost,
            hrd_corp_claimable=False,
            sdg_tags=(),
            skill_ids=course.skill_ids,
            hours=course.hours,
            hours_verified=course.hours_verified,
        )
        for course in load_courses()
    )


def get_skill(skill_id: str) -> Skill | None:
    return next((skill for skill in SKILLS if skill.skill_id == skill_id), None)


def get_role(role_id: str) -> Role | None:
    return next((role for role in ROLES if role.role_id == role_id), None)


def occupation_ids() -> set[str]:
    path = ROOT / "data" / "curated" / "target_occupations.csv"
    with path.open(newline="", encoding="utf-8") as file:
        return {row["occ_id"] for row in csv.DictReader(file)}
