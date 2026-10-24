"""Engine-backed implementations of the API routes (used when ENGINE_MODE=true).

Each function returns the same response models as the development fixtures, so
the frontend contract (API_CONTRACT.md) does not change; extra fields are optional.
"""
from __future__ import annotations

import csv
import io
import logging
import threading

import pandas as pd
from fastapi import HTTPException, UploadFile

from ..schemas import (
    ContextResponse,
    HrPersonaResponse,
    IndividualPersonaResponse,
    MatchedSkill,
    MatchRequest,
    MatchResponse,
    OccupationResponse,
    PersonasResponse,
    ProfileParseRequest,
    ProfileParseResponse,
    RoleMatch,
    SdgMappingResponse,
    Signal,
    SnapshotDiffRequest,
    SnapshotDiffResponse,
    SnapshotLoadRequest,
    SnapshotLoadResponse,
    CourseRecommendation,
    PathwayRequest,
    PathwayResponse,
    SignalBadge,
)
log = logging.getLogger("skillshift.api")
MAX_UPLOAD_BYTES = 2_000_000


_lock = threading.Lock()
_engine = None
_status = {"engine": "not started"}


def engine():
    """The process-wide Engine. Built once under a lock: the warm-up thread and the
    first requests arrive together, and a fresh clone must build the DB only once."""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from engine.service import Engine  # imported lazily: fixture mode needs no engine
                _status["engine"] = "starting"
                _engine = Engine()
    return _engine


def status() -> dict:
    return dict(_status)


def warm_up() -> None:
    """Build the DB and load the embedding model in the background at startup."""
    def run():
        _status["engine"] = "starting"
        try:
            engine().parse("use spreadsheets software")
            _status["engine"] = "ready"
            log.info("engine ready")
        except Exception as error:  # never block startup; requests retry on their own
            _status["engine"] = f"error: {error}"
            log.exception("engine warm-up failed")
    threading.Thread(target=run, daemon=True).start()


def _check_occupation(occ_id: str | None) -> None:
    if occ_id is not None and occ_id not in engine().store.occupation_ids:
        raise HTTPException(status_code=422, detail="Unknown occupation_id")


def _bad_request(error: KeyError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error.args[0]) if error.args else "invalid value")


def parse_profile(request: ProfileParseRequest) -> ProfileParseResponse:
    _check_occupation(request.occupation_id)
    found = engine().parse(request.text)
    return ProfileParseResponse(skills=[MatchedSkill(**f) for f in found],
                                assumption_note=engine().cfg["futures"]["assumption"])


async def parse_profile_file(file: UploadFile, occupation_id: str | None) -> ProfileParseResponse:
    _check_occupation(occupation_id)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 2 MB)")
    name = (file.filename or "").lower()
    if name.endswith(".pdf") or data[:4] == b"%PDF":
        import pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages[:10])
        except Exception as error:
            raise HTTPException(status_code=422, detail="Could not read this PDF") from error
    elif name.endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
    else:
        raise HTTPException(status_code=415, detail="Upload a PDF or a .txt file")
    if not text.strip():
        raise HTTPException(status_code=422, detail="No text found in the file (scanned PDFs are not supported)")
    return parse_profile(ProfileParseRequest(occupation_id=occupation_id, text=text[:20_000]))


def signals(skill_ids: list[str] | None, scenario: str, snapshot_id: str | None) -> list[Signal]:
    try:
        rows = engine().skill_signals(skill_ids or None, scenario=scenario, snapshot_id=snapshot_id)
    except KeyError as error:
        raise _bad_request(error) from error
    return [Signal(**r) for r in rows]


def match(request: MatchRequest) -> MatchResponse:
    _check_occupation(request.current_occupation_id)
    try:
        out = engine().match(request.skill_ids, current_occ=request.current_occupation_id,
                             scenario=request.scenario, sdg_preference=request.sdg_preference)
    except KeyError as error:
        raise _bad_request(error) from error
    return MatchResponse(roles=[RoleMatch(**r) for r in out["roles"]], assumption_note=out["assumption_note"],
                         snapshot_id=out["snapshot_id"], scenario=out["scenario"])


def load_snapshot(request: SnapshotLoadRequest) -> SnapshotLoadResponse:
    out = engine().load_snapshot(request.snapshot_id)
    from datetime import datetime, timezone
    return SnapshotLoadResponse(active_snapshot_id=out["active_snapshot_id"],
                                timestamp=datetime.now(timezone.utc).isoformat(), metadata=out["metadata"])


def diff(request: SnapshotDiffRequest, current_occupation_id: str | None = None,
         scenario: str = "moderate") -> SnapshotDiffResponse:
    _check_occupation(current_occupation_id)
    try:
        out = engine().diff(request.skill_ids, current_occ=current_occupation_id, scenario=scenario,
                            baseline=request.baseline_snapshot_id, new=request.new_snapshot_id)
    except KeyError as error:
        raise _bad_request(error) from error
    return SnapshotDiffResponse(**out)


def _v1_persona_occupations() -> dict[str, str]:
    from engine.config import CURATED
    with (CURATED / "persona_occupation_map.csv").open(encoding="utf-8", newline="") as f:
        return {r["persona_id"]: r["occ_id"] or None for r in csv.DictReader(f)}


def personas() -> PersonasResponse:
    data = engine().personas()
    occ = _v1_persona_occupations() if engine().cfg["curated_version"] == "v1" else {}
    keys_i = set(IndividualPersonaResponse.model_fields)
    keys_h = set(HrPersonaResponse.model_fields)
    return PersonasResponse(
        individual_users=[IndividualPersonaResponse(**{k: v for k, v in {**p, "current_occ_id": p.get("current_occ_id", occ.get(p["id"]))}.items() if k in keys_i})
                          for p in data["individual_users"]],
        hr_team_cohort=[HrPersonaResponse(**{k: v for k, v in {**p, "current_occ_id": p.get("current_occ_id", occ.get(p["id"]))}.items() if k in keys_h})
                        for p in data["hr_team_cohort"]],
    )


def occupations() -> list[OccupationResponse]:
    return [OccupationResponse(**o) for o in engine().occupations()]


def context(snapshot_id: str | None) -> ContextResponse:
    try:
        return ContextResponse(**engine().malaysia_context(snapshot_id))
    except KeyError as error:
        raise _bad_request(error) from error


def sdg() -> list[SdgMappingResponse]:
    """SDG links of the active curated version (v2: per target occupation)."""
    rows = engine().store["sdg_map"]
    titles = engine().store.occ_title
    out = []
    for r in rows.itertuples():
        if (
            r.key_type == "skill_collection"
            or not r.sdg_ids
            or not getattr(r, "occ_id", "")
        ):
            continue
        name = titles.get(r.occ_id, r.key)
        link = "; ".join(f"SDG {g}" for g in str(r.sdg_ids).split(";") if g)
        out.append(SdgMappingResponse(
            occupation=name,
            sdg_link=link,
            reasoning=r.reason,
            status=getattr(r, "status", "") or "curated",
            basis=getattr(r, "basis", "") or "curated occupation mapping",
            evidence=getattr(r, "evidence", "") or r.reason,
            source=getattr(r, "source", "") or "UN SDG / ESCO Mapping",
            date=getattr(r, "date_published", "") or "2026-10",
        ))
    return out


def pathway(request: PathwayRequest) -> PathwayResponse:
    _check_occupation(request.target_role_id)
    store = engine().store
    essentials = engine().essentials.get(request.target_role_id, [])
    valid_skills = [skill_id for skill_id in request.skill_ids if skill_id in store.skill_ids]
    missing = [skill_id for skill_id in essentials if skill_id not in valid_skills]
    courses = store["courses"]
    rows = []
    sdg_rows = store["sdg_map"]
    role_sdg = sdg_rows[
        (sdg_rows.key_type == "occupation")
        & (sdg_rows.occ_id == request.target_role_id)
    ]
    sdg_tags = [
        f"SDG {value}"
        for value in str(role_sdg.iloc[0].sdg_ids).split(";")
        if value
    ] if not role_sdg.empty and role_sdg.iloc[0].sdg_ids else []
    for skill_id in missing:
        matched = courses[
            courses.esco_skill_uris.fillna("").str.split(";").apply(
                lambda values: skill_id in values
            )
        ]
        for row in matched.itertuples():
            verified = bool(row.hours_verified)
            hours = int(row.hours) if verified and pd.notna(row.hours) else "hours not verified"
            marginal = round(1 / (len(essentials) * row.hours), 4) if verified and row.hours else None
            rows.append(CourseRecommendation(
                course_id=row.course_id,
                title=row.title,
                provider=row.provider,
                url=row.url,
                cost=int(row.cost_myr),
                hrd_corp_claimable=None if row.hrd_claimable == "unknown" else row.hrd_claimable == "true",
                sdg_tags=sdg_tags,
                hours=hours,
                hours_verified=verified,
                marginal_score_per_hour=marginal,
                source_badges=[SignalBadge(source="data/curated/courses_v2.csv", date=str(row.checked_on))],
            ))
    if not rows:
        matched = courses[courses.relevant_to_targets.astype(str).str.lower() == "true"].head(10)
        for row in matched.itertuples():
            verified = bool(row.hours_verified)
            hours = int(row.hours) if verified and pd.notna(row.hours) else "hours not verified"
            marginal = round(1 / (len(essentials) * row.hours), 4) if verified and row.hours else None
            rows.append(CourseRecommendation(
                course_id=row.course_id,
                title=row.title,
                provider=row.provider,
                url=row.url,
                cost=int(row.cost_myr),
                hrd_corp_claimable=None if row.hrd_claimable == "unknown" else row.hrd_claimable == "true",
                sdg_tags=sdg_tags,
                hours=hours,
                hours_verified=verified,
                marginal_score_per_hour=marginal,
                source_badges=[SignalBadge(source="data/curated/courses_v2.csv", date=str(row.checked_on))],
            ))
    unique = {item.course_id: item for item in rows}
    ordered = sorted(
        unique.values(),
        key=lambda item: item.marginal_score_per_hour
        if item.marginal_score_per_hour is not None else -1,
        reverse=True,
    )
    return PathwayResponse(
        target_role_id=request.target_role_id,
        missing_skills=missing,
        pathway=ordered,
        best_next_hour=next(
            (item for item in ordered if item.marginal_score_per_hour is not None),
            None,
        ),
        assumption_note=engine().cfg["futures"]["assumption"],
    )
