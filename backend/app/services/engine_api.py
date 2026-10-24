"""Engine-backed implementations of the API routes (used when ENGINE_MODE=true).

Each function returns the same response models as the development fixtures, so
the frontend contract (API_CONTRACT.md) does not change; extra fields are optional.
"""
from __future__ import annotations

import csv
import io
import logging
import threading

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
    UpgradeRequest,
    UpgradeResponse,
    XrayResponse,
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
from . import runpod_client

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
    remote_ids = runpod_client.extract_skill_ids(request.text)
    if remote_ids:
        valid_ids = [skill_id for skill_id in remote_ids if skill_id in engine().store.skill_ids]
        if valid_ids:
            return ProfileParseResponse(
                skills=[
                    MatchedSkill(
                        skill_id=skill_id,
                        skill_name=engine().store.skill_label[skill_id],
                        extracted_phrase="RunPod extraction",
                        confidence=0.8,
                        status="suggested",
                    )
                    for skill_id in dict.fromkeys(valid_ids)
                ],
                assumption_note=engine().cfg["futures"]["assumption"],
            )
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
    """P2 learning pathway from the engine (engine/service.py: Engine.pathway).

    Missing essential skills in learning order (broader ESCO concepts first, then by
    score gain), one course per skill, best_next_hour from verified hours only.
    Every course carries the page it was checked on and the check date.
    """
    _check_occupation(request.target_role_id)
    _check_occupation(request.current_occupation_id)
    try:
        out = engine().pathway(request.skill_ids, request.target_role_id,
                               current_occ=request.current_occupation_id, scenario=request.scenario)
    except KeyError as error:
        raise _bad_request(error) from error

    def course(c: dict) -> CourseRecommendation:
        badge = SignalBadge(source=f"Course page, {c['provider']}" if c["hours_verified"] else
                            f"Course link, {c['provider']} (hours not on the page)",
                            date=c.get("checked_on") or "", url=c["url"], date_kind="retrieved")
        return CourseRecommendation(**c, source_badges=[badge])

    items = [course(c) for c in out["pathway"]]
    if request.sdg_filter:
        items = [c for c in items if request.sdg_filter in c.sdg_tags]
    best = out["best_next_hour"]
    return PathwayResponse(
        target_role_id=out["target_role_id"], target_role_title=out["target_role_title"],
        missing_skills=out["missing_skills"], pathway=items,
        best_next_hour=next((c for c in items if best and c.course_id == best["course_id"]), None),
        skills_without_course=out["skills_without_course"], totals=out["totals"],
        assumption_note=out["assumption_note"],
    )


def xray(occupation: str, snapshot_id: str | None) -> XrayResponse:
    """H1 Task X-ray of an occupation (engine/service.py: Engine.xray)."""
    _check_occupation(occupation)
    try:
        return XrayResponse(**engine().xray(occupation, snapshot_id))
    except KeyError as error:
        raise _bad_request(error) from error


def upgrade(request: UpgradeRequest) -> UpgradeResponse:
    """H2 upgrade in place (engine/service.py: Engine.upgrade)."""
    _check_occupation(request.occupation_id)
    try:
        return UpgradeResponse(**engine().upgrade(request.occupation_id, request.skill_ids,
                                                  scenario=request.scenario))
    except KeyError as error:
        raise _bad_request(error) from error
