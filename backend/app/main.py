from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
    SdgMappingResponse,
    PersonasResponse,
    IndividualPersonaResponse,
    HrPersonaResponse,
    OccupationResponse,
    ContextResponse,
    UpgradeRequest,
    UpgradeResponse,
    XrayResponse,
)
from .services import engine_api
from .services import runpod_client
from .services.extraction import extract_skills, normalize_skill_phrases
from .services.guardrails import validate_db_ids
from .services.repository import (
    ROLES,
    courses_for_skill,
    get_role,
    get_skill,
    normalize_backend_skill_ids,
    occupation_ids,
)
from .services.simulation import simulate_role_robustness
from .services.curated_data import (
    load_demand_signals,
    load_personas,
    load_sdg_mappings,
)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.engine_mode:
        engine_api.warm_up()  # load DB + embedding model in the background
    yield


app = FastAPI(title="Future Skills Compass API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origin.split(",") if origin.strip()],
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
@app.get("/api/health")
def health() -> dict[str, object]:
    mode = "engine" if settings.engine_mode else "fixtures" if settings.dev_mode else "off"
    return {
        "status": "ok",
        "mode": mode,
        **runpod_client.provider_status(),
        **(engine_api.status() if settings.engine_mode else {}),
    }


@app.post("/api/profile/parse", response_model=ProfileParseResponse)
def parse_profile(request: ProfileParseRequest) -> ProfileParseResponse:
    if settings.engine_mode:
        return engine_api.parse_profile(request)
    ensure_dev_mode()
    if request.occupation_id and request.occupation_id not in occupation_ids():
        raise HTTPException(status_code=422, detail="Unknown occupation_id")
    valid_ids = validate_db_ids(
        [skill.skill_id for skill, _, _ in extract_skills(request.text)]
        + [skill.skill_id for skill, _, _ in normalize_skill_phrases(request.current_skills)],
        kind="skill",
    )
    matches: list[MatchedSkill] = []
    seen: set[str] = set()
    for skill, phrase, confidence in (
        extract_skills(request.text) + normalize_skill_phrases(request.current_skills)
    ):
        if skill.skill_id not in valid_ids or skill.skill_id in seen:
            continue
        matches.append(
            MatchedSkill(
                skill_id=skill.skill_id,
                skill_name=skill.skill_name,
                extracted_phrase=phrase,
                confidence=confidence,
            )
        )
        seen.add(skill.skill_id)
    return ProfileParseResponse(skills=matches, assumption_note=settings.assumption_note)


@app.post("/api/profile/parse_file", response_model=ProfileParseResponse)
async def parse_profile_file(
    file: UploadFile = File(...), occupation_id: str | None = Form(default=None)
) -> ProfileParseResponse:
    """CV upload (PDF or .txt). Engine mode only."""
    if not settings.engine_mode:
        raise HTTPException(status_code=503, detail="CV upload needs ENGINE_MODE=true.")
    return await engine_api.parse_profile_file(file, occupation_id)


@app.get("/api/signals", response_model=list[Signal])
def signals(
    skill: list[str] | None = Query(default=None),
    scenario: str = "moderate",
    snapshot_id: str | None = None,
) -> list[Signal]:
    """Engine mode: Skills Radar (momentum per skill). Fixtures: demand rows."""
    if settings.engine_mode:
        return engine_api.signals(skill, scenario, snapshot_id)
    ensure_dev_mode()
    return [
        Signal(
            id=f"demand-{signal.occupation.lower().replace(' ', '-')}",
            name=signal.occupation,
            value=signal.growth_rate_pct,
            status=signal.category.lower().split("/")[0],
            base_vacancies_2025=signal.base_vacancies_2025,
            projected_vacancies_2026=signal.projected_vacancies_2026,
            growth_rate_pct=signal.growth_rate_pct,
            source=SignalBadge(source=signal.source, date=signal.date_published),
        )
        for signal in load_demand_signals()
    ]


@app.get("/api/sdg", response_model=list[SdgMappingResponse])
def sdg_mappings() -> list[SdgMappingResponse]:
    if settings.engine_mode:
        return engine_api.sdg()
    ensure_dev_mode()
    return [SdgMappingResponse(**mapping.__dict__) for mapping in load_sdg_mappings()]


def role_sdg_links(role_title: str) -> list[str]:
    """Return evidence-backed SDG links without joining unrelated occupations."""
    title_words = {
        word.casefold()
        for word in role_title.replace("-", " ").replace("_", " ").split()
        if len(word) > 3
    }
    mappings = load_sdg_mappings()
    ranked = sorted(
        mappings,
        key=lambda mapping: len(
            title_words.intersection(
                {
                    word.casefold()
                    for word in mapping.occupation.replace("-", " ").replace("_", " ").split()
                    if len(word) > 3
                }
            )
        ),
        reverse=True,
    )
    best = [
        mapping.sdg_link
        for mapping in ranked
        if title_words.intersection(
            {
                word.casefold()
                for word in mapping.occupation.replace("-", " ").replace("_", " ").split()
                if len(word) > 3
            }
        )
    ]
    return list(dict.fromkeys(best[:3]))


@app.get("/api/personas", response_model=PersonasResponse)
def personas() -> PersonasResponse:
    if settings.engine_mode:
        return engine_api.personas()
    ensure_dev_mode()
    individuals, hr_cohort = load_personas()
    return PersonasResponse(
        individual_users=[
            IndividualPersonaResponse(
                **{
                    **persona.__dict__,
                    "current_skills": list(persona.current_skills),
                    "normalized_skill_ids": [
                        skill.skill_id
                        for skill, _, _ in normalize_skill_phrases(persona.current_skills)
                    ],
                }
            )
            for persona in individuals
        ],
        hr_team_cohort=[
            HrPersonaResponse(
                **{
                    **persona.__dict__,
                    "current_skills": list(persona.current_skills),
                    "normalized_skill_ids": [
                        skill.skill_id
                        for skill, _, _ in normalize_skill_phrases(persona.current_skills)
                    ],
                }
            )
            for persona in hr_cohort
        ],
    )


@app.post("/api/match", response_model=MatchResponse)
def match(request: MatchRequest) -> MatchResponse:
    if settings.engine_mode:
        return engine_api.match(request)
    ensure_dev_mode()
    skill_ids = normalize_backend_skill_ids(
        set(validate_db_ids(request.skill_ids, kind="skill"))
    )
    robustness = simulate_role_robustness(ROLES, set(skill_ids))
    roles: list[RoleMatch] = []
    for role in ROLES:
        sdg_tags = role_sdg_links(role.role_title)
        matched = sorted(set(skill_ids).intersection(role.skill_ids))
        missing = sorted(set(role.skill_ids).difference(skill_ids))
        covered = len(matched) / len(role.skill_ids)
        base_score = covered * 0.65 + role.trend * 0.35
        sdg_score = min(len(sdg_tags) / 3, 1.0)
        score = round(
            ((base_score * (1 - (request.sdg_preference or 0)))
             + (sdg_score * (request.sdg_preference or 0))) * 100,
            2,
        )
        roles.append(
            RoleMatch(
                role_id=role.role_id,
                role_title=role.role_title,
                total_match_score=score,
                score_breakdown={
                    "skills_covered_score": round(covered * 100, 2),
                    "role_trend_score": round(role.trend * 100, 2),
                    "transferability_score": round((1 - len(missing) / len(role.skill_ids)) * 100, 2),
                    "sdg_preference_score": round(sdg_score * 100, 2),
                },
                matched_skills=matched,
                missing_skills=missing,
                sdg_tags=sdg_tags,
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
    if settings.engine_mode:
        return engine_api.pathway(request)
    ensure_dev_mode()
    role = get_role(request.target_role_id)
    if role is None:
        raise HTTPException(status_code=422, detail="Unknown target_role_id")
    skill_ids = normalize_backend_skill_ids(
        set(validate_db_ids(request.skill_ids, kind="skill"))
    )
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
                    sdg_tags=role_sdg_links(role.role_title),
                    hours=hours,
                    hours_verified=course.hours_verified,
                    marginal_score_per_hour=marginal,
                    source_badges=[
                        SignalBadge(source=course.source, date=course.date)
                    ],
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
    if settings.engine_mode:
        return engine_api.load_snapshot(request)
    ensure_dev_mode()
    return SnapshotLoadResponse(
        active_snapshot_id=request.snapshot_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata={"source": "Synthetic development fixture", "status": "development"},
    )


@app.post("/api/snapshot/diff", response_model=SnapshotDiffResponse)
def diff_snapshot(request: SnapshotDiffRequest) -> SnapshotDiffResponse:
    if settings.engine_mode:
        return engine_api.diff(request, request.current_occupation_id, request.scenario)
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


@app.get("/api/occupations", response_model=list[OccupationResponse])
def occupations() -> list[OccupationResponse]:
    """Target occupations for the 'current job' picker. Engine mode only."""
    if not settings.engine_mode:
        raise HTTPException(status_code=503, detail="Needs ENGINE_MODE=true.")
    return engine_api.occupations()


@app.get("/api/context", response_model=ContextResponse)
def context(snapshot_id: str | None = None) -> ContextResponse:
    """Malaysia vs global AI-usage context from the active AEI snapshot. Engine mode only."""
    if not settings.engine_mode:
        raise HTTPException(status_code=503, detail="Needs ENGINE_MODE=true.")
    return engine_api.context(snapshot_id)


@app.get("/api/xray", response_model=XrayResponse)
def xray(occupation: str, snapshot_id: str | None = None) -> XrayResponse:
    """Task X-ray of a job: each O*NET task labelled automating / assisting / mostly human. Engine mode only."""
    if not settings.engine_mode:
        raise HTTPException(status_code=503, detail="Needs ENGINE_MODE=true.")
    return engine_api.xray(occupation, snapshot_id)


@app.post("/api/upgrade", response_model=UpgradeResponse)
def upgrade(request: UpgradeRequest) -> UpgradeResponse:
    """Upgrade in place: skills of the current job behind its AI-assisted tasks. Engine mode only."""
    if not settings.engine_mode:
        raise HTTPException(status_code=503, detail="Needs ENGINE_MODE=true.")
    return engine_api.upgrade(request)


# Serve the built frontend (frontend/dist) from the same process and port, e.g. on
# Replit. Mounted last so every /api route above takes precedence.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
