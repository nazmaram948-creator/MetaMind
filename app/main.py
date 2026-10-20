from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .schemas import (
    MatchRequest,
    MatchResponse,
    MatchedSkill,
    CourseRecommendation,
    PathwayRequest,
    PathwayResponse,
    ProfileParseRequest,
    ProfileParseResponse,
    RoleMatch,
    Signal,
    SignalBadge,
    SnapshotDiffRequest,
    SnapshotDiffResponse,
    SnapshotLoadRequest,
    SnapshotLoadResponse,
)
from .services.extraction import extract_skills
from .services.guardrails import validate_db_ids
from .services.repository import ROLES, courses_for_skill, get_role, get_skill, occupation_ids
from .services.simulation import simulate_role_robustness

app = FastAPI(title="Future Skills Compass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BADGE = SignalBadge(source="Synthetic development fixture", date="2026-10")


def ensure_dev_mode() -> None:
    if not settings.dev_mode:
        raise HTTPException(
            status_code=503,
            detail="Development fixtures are disabled; configure the verified data store.",
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/profile/parse", response_model=ProfileParseResponse)
def parse_profile(request: ProfileParseRequest) -> ProfileParseResponse:
    ensure_dev_mode()
    if request.occupation_id and request.occupation_id not in occupation_ids():
        raise HTTPException(status_code=422, detail="Unknown occupation_id")
    matches = [
        MatchedSkill(
            skill_id=skill.skill_id,
            skill_name=skill.skill_name,
            extracted_phrase=phrase,
            confidence=confidence,
        )
        for skill, phrase, confidence in extract_skills(request.text)
        if skill.skill_id in validate_db_ids([skill.skill_id], kind="skill")
    ]
    return ProfileParseResponse(skills=matches, assumption_note=settings.assumption_note)


@app.get("/api/signals", response_model=list[Signal])
def signals() -> list[Signal]:
    ensure_dev_mode()
    return [
        Signal(id="skill-data-analysis", name="Data analysis", value=0.74, status="rising", source=BADGE),
        Signal(id="skill-spreadsheets", name="Spreadsheet software", value=0.51, status="stable", source=BADGE),
        Signal(id="skill-customer-service", name="Customer service", value=0.38, status="declining", source=BADGE),
    ]


@app.post("/api/match", response_model=MatchResponse)
def match(request: MatchRequest) -> MatchResponse:
    ensure_dev_mode()
    skill_ids = validate_db_ids(request.skill_ids, kind="skill")
    robustness = simulate_role_robustness(ROLES, set(skill_ids))
    roles: list[RoleMatch] = []
    for role in ROLES:
        matched = sorted(set(skill_ids).intersection(role.skill_ids))
        missing = sorted(set(role.skill_ids).difference(skill_ids))
        covered = len(matched) / len(role.skill_ids)
        score = round((covered * 0.65 + role.trend * 0.35) * 100, 2)
        roles.append(
            RoleMatch(
                role_id=role.role_id,
                role_title=role.role_title,
                total_match_score=score,
                score_breakdown={
                    "skills_covered_score": round(covered * 100, 2),
                    "role_trend_score": round(role.trend * 100, 2),
                    "transferability_score": round((1 - len(missing) / len(role.skill_ids)) * 100, 2),
                },
                matched_skills=matched,
                missing_skills=missing,
                robustness_estimate=(
                    f"Estimate: stays in your top 5 in "
                    f"{round(robustness[role.role_id]['top5_frequency'] * 100)}% "
                    "of simulated futures"
                ),
                robustness=robustness[role.role_id],
                source_badges=[BADGE],
            )
        )
    roles.sort(key=lambda role: role.total_match_score, reverse=True)
    return MatchResponse(roles=roles, assumption_note=settings.assumption_note)


@app.post("/api/pathway", response_model=PathwayResponse)
def pathway(request: PathwayRequest) -> PathwayResponse:
    ensure_dev_mode()
    role = get_role(request.target_role_id)
    if role is None:
        raise HTTPException(status_code=422, detail="Unknown target_role_id")
    skill_ids = set(validate_db_ids(request.skill_ids, kind="skill"))
    missing_skills = sorted(set(role.skill_ids).difference(skill_ids))
    recommendations: list[CourseRecommendation] = []
    for skill_id in missing_skills:
        for course in courses_for_skill(skill_id):
            if request.sdg_filter and request.sdg_filter not in course.sdg_tags:
                continue
            valid_course_id = validate_db_ids([course.course_id], kind="course")
            if not valid_course_id:
                continue
            verified = course.hours_verified is True and course.hours is not None
            hours: float | str = course.hours if verified else "hours not verified"
            marginal = None
            if verified:
                marginal = round((1 / len(role.skill_ids)) / course.hours, 4)
            recommendations.append(
                CourseRecommendation(
                    course_id=course.course_id,
                    title=course.title,
                    provider=course.provider,
                    url=course.url,
                    cost=course.cost,
                    hrd_corp_claimable=course.hrd_corp_claimable,
                    sdg_tags=list(course.sdg_tags),
                    hours=hours,
                    hours_verified=course.hours_verified,
                    marginal_score_per_hour=marginal,
                )
            )
    recommendations.sort(
        key=lambda item: item.marginal_score_per_hour
        if item.marginal_score_per_hour is not None
        else -1,
        reverse=True,
    )
    return PathwayResponse(
        target_role_id=role.role_id,
        missing_skills=missing_skills,
        pathway=recommendations,
        best_next_hour=recommendations[0] if recommendations and recommendations[0].marginal_score_per_hour is not None else None,
        assumption_note=settings.assumption_note,
    )


@app.post("/api/snapshot/load", response_model=SnapshotLoadResponse)
def load_snapshot(request: SnapshotLoadRequest) -> SnapshotLoadResponse:
    ensure_dev_mode()
    return SnapshotLoadResponse(
        active_snapshot_id=request.snapshot_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"source": "Synthetic development fixture", "status": "development"},
    )


@app.post("/api/snapshot/diff", response_model=SnapshotDiffResponse)
def diff_snapshot(request: SnapshotDiffRequest) -> SnapshotDiffResponse:
    ensure_dev_mode()
    valid_skills = validate_db_ids(request.skill_ids, kind="skill")
    return SnapshotDiffResponse(
        baseline_snapshot_id=request.baseline_snapshot_id,
        new_snapshot_id=request.new_snapshot_id,
        changes=[
            {
                "role_id": role.role_id,
                "movement": 0,
                "explanation": f"No measured change for {role.role_title}; "
                f"{len(valid_skills)} verified skills supplied.",
                "source": BADGE.model_dump(),
            }
            for role in ROLES
        ],
        assumption_note=settings.assumption_note,
    )
