"""Engine-backed implementations of the API routes (used when ENGINE_MODE=true).

Each function returns the same response models as the development fixtures, so
the frontend contract (API_CONTRACT.md) does not change; extra fields are optional.
"""
from __future__ import annotations

import csv
import io
import logging
import threading
from functools import lru_cache

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
)

log = logging.getLogger("skillshift.api")
MAX_UPLOAD_BYTES = 2_000_000


@lru_cache(maxsize=1)
def engine():
    from engine.service import Engine  # imported lazily: fixture mode needs no engine
    return Engine()


def warm_up() -> None:
    """Load the DB and the embedding model in the background at startup."""
    def run():
        try:
            engine().parse("use spreadsheets software")
            log.info("engine ready")
        except Exception:  # never block startup; the first request will retry
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
        if r.key_type == "skill_collection" or not r.sdg_ids:
            continue
        name = titles.get(r.occ_id, r.key)
        link = "; ".join(f"SDG {g}" for g in str(r.sdg_ids).split(";") if g)
        out.append(SdgMappingResponse(occupation=name, sdg_link=link, reasoning=r.reason))
    return out
