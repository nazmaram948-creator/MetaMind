from dataclasses import dataclass
from pathlib import Path
import csv


ROOT = Path(__file__).resolve().parents[2]


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
    cost: str
    hrd_corp_claimable: bool
    sdg_tags: tuple[str, ...]
    skill_ids: tuple[str, ...]
    hours: float | None
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
        "free",
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
        "free",
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
    return [course for course in course_catalogue() if skill_id in course.skill_ids]


def course_catalogue() -> tuple[Course, ...]:
    """Load Walid's catalogue when available, otherwise use dev fixtures."""
    path = ROOT / "data" / "curated" / "courses.csv"
    if not path.exists():
        return COURSES
    courses: list[Course] = []
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            hours_value = row.get("hours", "").strip()
            verified_value = row.get("hours_verified", "").strip().lower()
            courses.append(
                Course(
                    course_id=row["course_id"],
                    title=row["title"],
                    provider=row["provider"],
                    url=row["url"],
                    cost=row["cost"],
                    hrd_corp_claimable=row.get("hrd_corp_claimable", "").strip().lower()
                    in {"true", "1", "yes"},
                    sdg_tags=tuple(filter(None, row.get("sdg_tags", "").split(";"))),
                    skill_ids=tuple(filter(None, row.get("skill_ids", "").split(";"))),
                    hours=float(hours_value) if hours_value else None,
                    hours_verified=(
                        True if verified_value in {"true", "1", "yes"} else
                        False if verified_value in {"false", "0", "no"} else None
                    ),
                )
            )
    return tuple(courses)


def get_skill(skill_id: str) -> Skill | None:
    return next((skill for skill in SKILLS if skill.skill_id == skill_id), None)


def get_role(role_id: str) -> Role | None:
    return next((role for role in ROLES if role.role_id == role_id), None)


def occupation_ids() -> set[str]:
    path = ROOT / "data" / "curated" / "target_occupations.csv"
    with path.open(newline="", encoding="utf-8") as file:
        return {row["occ_id"] for row in csv.DictReader(file)}
