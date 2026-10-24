from dataclasses import dataclass
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CURATED = ROOT / "data" / "curated"


@dataclass(frozen=True)
class DemandSignal:
    occupation: str
    base_vacancies_2025: int
    projected_vacancies_2026: int
    growth_rate_pct: float
    category: str
    source: str
    date_published: str


@dataclass(frozen=True)
class CuratedCourse:
    course_id: str
    course_title: str
    provider: str
    skill_ids: tuple[str, ...]
    hours: int
    hours_verified: bool
    cost: int
    url: str


@dataclass(frozen=True)
class SdgMapping:
    occupation: str
    sdg_link: str
    reasoning: str
    basis: str
    evidence: str
    status: str
    source: str
    date: str


@dataclass(frozen=True)
class IndividualPersona:
    id: str
    name: str
    persona_type: str
    current_role: str | None
    industry: str
    experience_years: int
    current_skills: tuple[str, ...]
    cv_text: str


@dataclass(frozen=True)
class HrPersona:
    id: str
    name: str
    current_role: str
    current_skills: tuple[str, ...]


def _rows(filename: str, expected: set[str]) -> list[dict[str, str]]:
    path = CURATED / filename
    if not path.exists():
        raise FileNotFoundError(f"Curated data file is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        headers = set(reader.fieldnames or ())
        if headers != expected:
            raise ValueError(
                f"{filename} columns do not match schema: "
                f"expected {sorted(expected)}, got {sorted(headers)}"
            )
        return list(reader)


def _int(row: dict[str, str], field: str, filename: str) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{filename}.{field} must be an integer") from error


def _float(row: dict[str, str], field: str, filename: str) -> float:
    try:
        return float(row[field])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{filename}.{field} must be a number") from error


def _bool(row: dict[str, str], field: str, filename: str) -> bool:
    value = row.get(field, "").strip().lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{filename}.{field} must be TRUE or FALSE")
    return value == "true"


def load_demand_signals() -> tuple[DemandSignal, ...]:
    filename = "malaysian_job_demand_real.csv"
    expected = {
        "occupation", "base_vacancies_2025", "projected_vacancies_2026",
        "growth_rate_pct", "category", "source", "date_published",
    }
    return tuple(
        DemandSignal(
            occupation=row["occupation"],
            base_vacancies_2025=_int(row, "base_vacancies_2025", filename),
            projected_vacancies_2026=_int(row, "projected_vacancies_2026", filename),
            growth_rate_pct=_float(row, "growth_rate_pct", filename),
            category=row["category"],
            source=row["source"],
            date_published=row["date_published"],
        )
        for row in _rows(filename, expected)
    )


def load_courses() -> tuple[CuratedCourse, ...]:
    filename = "courses.csv"
    expected = {
        "course_id", "course_title", "provider", "skill_ids", "hours",
        "hours_verified", "cost", "url",
    }
    return tuple(
        CuratedCourse(
            course_id=row["course_id"],
            course_title=row["course_title"],
            provider=row["provider"],
            skill_ids=tuple(skill_id for skill_id in row["skill_ids"].split(";") if skill_id),
            hours=_int(row, "hours", filename),
            hours_verified=_bool(row, "hours_verified", filename),
            cost=_int(row, "cost", filename),
            url=row["url"],
        )
        for row in _rows(filename, expected)
    )


def load_sdg_mappings() -> tuple[SdgMapping, ...]:
    v2 = CURATED / "sdg_map_v2.csv"
    filename = "sdg_map_v2.csv" if v2.exists() else "sdg_mapping.csv"
    if v2.exists():
        expected_v2 = {
            "key_type", "key", "occ_id", "isco_code", "esco_uri", "sdg_ids",
            "targets", "reason", "evidence", "basis", "status",
            "source", "date_published",
        }
        rows = _rows(filename, expected_v2)
        return tuple(
            SdgMapping(
                occupation=row["key"],
                sdg_link="; ".join(
                    f"SDG {value}" for value in row["sdg_ids"].split(";") if value
                ),
                reasoning=row["reason"],
                basis=row["basis"],
                evidence=row["evidence"],
                status=row["status"],
                source=filename,
                date="undated",
            )
            for row in rows
            if row["key_type"] == "occupation"
        )
    expected = {"occupation", "sdg_link", "reasoning"}
    rows = _rows(filename, expected)
    return tuple(
        SdgMapping(
            occupation=row["occupation"],
            sdg_link=row["sdg_link"],
            reasoning=row["reasoning"],
            basis=row.get("basis", "curated occupation mapping"),
            evidence=row.get("evidence", row["reasoning"]),
            status=row.get("status", "curated"),
            source=row.get("source", filename),
            date=row.get("date_published", row.get("date", "undated")),
        )
        for row in rows
    )


def load_personas() -> tuple[tuple[IndividualPersona, ...], tuple[HrPersona, ...]]:
    path = CURATED / "synthetic_personas.json"
    if not path.exists():
        raise FileNotFoundError(f"Curated data file is missing: {path}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8-sig"))
    if set(data) != {"individual_users", "hr_team_cohort"}:
        raise ValueError("synthetic_personas.json must contain individual_users and hr_team_cohort")
    individuals = tuple(
        IndividualPersona(
            id=item["id"],
            name=item["name"],
            persona_type=item["persona_type"],
            current_role=item["current_role"],
            industry=item["industry"],
            experience_years=int(item["experience_years"]),
            current_skills=tuple(item["current_skills"]),
            cv_text=item["cv_text"],
        )
        for item in data["individual_users"]
    )
    hr_cohort = tuple(
        HrPersona(
            id=item["id"],
            name=item["name"],
            current_role=item["current_role"],
            current_skills=tuple(item["current_skills"]),
        )
        for item in data["hr_team_cohort"]
    )
    return individuals, hr_cohort
