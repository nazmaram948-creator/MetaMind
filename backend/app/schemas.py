from typing import Literal

from pydantic import BaseModel, Field


Scenario = Literal["moderate", "fast"]


class ProfileParseRequest(BaseModel):
    occupation_id: str | None = None
    text: str = Field(default="", max_length=20_000)
    current_skills: list[str] = Field(default_factory=list, max_length=100)


class MatchedSkill(BaseModel):
    skill_id: str
    skill_name: str
    extracted_phrase: str
    confidence: float


class ProfileParseResponse(BaseModel):
    skills: list[MatchedSkill]
    label: Literal["Estimate"] = "Estimate"
    assumption_note: str


class SignalBadge(BaseModel):
    source: str
    date: str


class Signal(BaseModel):
    id: str
    name: str
    value: float
    status: Literal["rising", "stable", "declining"]
    base_vacancies_2025: int | None = None
    projected_vacancies_2026: int | None = None
    growth_rate_pct: float | None = None
    label: Literal["Estimate"] = "Estimate"
    source: SignalBadge


class MatchRequest(BaseModel):
    skill_ids: list[str] = Field(default_factory=list)
    current_occupation_id: str | None = None
    scenario: Scenario = "moderate"
    sdg_preference: float | None = Field(default=None, ge=0, le=1)


class RoleMatch(BaseModel):
    role_id: str
    role_title: str
    total_match_score: float
    score_breakdown: dict[str, float]
    matched_skills: list[str]
    missing_skills: list[str]
    sdg_tags: list[str]
    robustness_estimate: str
    robustness: dict[str, object]
    source_badges: list[SignalBadge]
    is_estimate: Literal[True] = True


class MatchResponse(BaseModel):
    roles: list[RoleMatch]
    label: Literal["Estimate"] = "Estimate"
    assumption_note: str


class CourseRecommendation(BaseModel):
    course_id: str
    title: str
    provider: str
    url: str
    cost: int
    hrd_corp_claimable: bool | None
    sdg_tags: list[str]
    hours: int | str
    hours_verified: bool | None
    marginal_score_per_hour: float | None
    source_badges: list[SignalBadge]


class PathwayRequest(BaseModel):
    skill_ids: list[str] = Field(default_factory=list)
    target_role_id: str
    sdg_filter: str | None = None


class PathwayResponse(BaseModel):
    target_role_id: str
    missing_skills: list[str]
    pathway: list[CourseRecommendation]
    best_next_hour: CourseRecommendation | None
    label: Literal["Estimate"] = "Estimate"
    assumption_note: str


class SdgMappingResponse(BaseModel):
    occupation: str
    sdg_link: str
    reasoning: str
    status: str
    basis: str
    evidence: str
    source: str
    date: str


class IndividualPersonaResponse(BaseModel):
    id: str
    name: str
    persona_type: str
    current_role: str | None
    industry: str
    experience_years: int
    current_skills: list[str]
    normalized_skill_ids: list[str]
    cv_text: str


class HrPersonaResponse(BaseModel):
    id: str
    name: str
    current_role: str
    current_skills: list[str]
    normalized_skill_ids: list[str]


class PersonasResponse(BaseModel):
    individual_users: list[IndividualPersonaResponse]
    hr_team_cohort: list[HrPersonaResponse]


class SnapshotLoadRequest(BaseModel):
    snapshot_id: Literal["baseline_snapshot", "latest_snapshot"]


class SnapshotLoadResponse(BaseModel):
    status: Literal["loaded"] = "loaded"
    active_snapshot_id: str
    timestamp: str
    metadata: dict[str, str]


class SnapshotDiffRequest(BaseModel):
    skill_ids: list[str] = Field(default_factory=list)
    baseline_snapshot_id: str = "baseline_snapshot"
    new_snapshot_id: str = "latest_snapshot"


class SnapshotDiffResponse(BaseModel):
    baseline_snapshot_id: str
    new_snapshot_id: str
    changes: list[dict[str, object]]
    label: Literal["Estimate"] = "Estimate"
    assumption_note: str
