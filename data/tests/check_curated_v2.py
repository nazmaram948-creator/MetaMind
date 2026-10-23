"""Integrity checks for the v2 curated files (the team's v1 files are not touched).

Run:  pytest data/tests/check_curated_v2.py -q
(Named check_*.py on purpose, so the backend suite does not collect it.)
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CURATED = ROOT / "data" / "curated"
EXTRACTS = ROOT / "data" / "extracts"

FORBIDDEN_PERSONA_KEYS = {"age", "gender", "sex", "dob", "date_of_birth", "ic", "nric",
                          "phone", "email", "address"}
NRIC = re.compile(r"\b\d{6}-\d{2}-\d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\b(?:\+?60|0)1\d[- ]?\d{3,4}[- ]?\d{4}\b")


def rows(name: str, folder: Path = CURATED) -> list[dict]:
    with (folder / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def occ_ids() -> set[str]:
    return {r["occ_id"] for r in rows("target_occupations.csv")}


@pytest.fixture(scope="module")
def esco_skill_uris() -> set[str]:
    return {r["uri"] for r in rows("esco_skills.csv", EXTRACTS)}


def test_target_occupations_link_to_esco(occ_ids):
    targets = rows("target_occupations.csv")
    assert len(occ_ids) == len(targets), "duplicate occ_id"
    esco = {r["uri"] for r in rows("esco_occupations.csv", EXTRACTS)}
    assert {t["esco_uri"] for t in targets} <= esco
    for t in targets:
        for soc in t["onet_soc"].split(";"):
            assert re.fullmatch(r"\d{2}-\d{4}\.\d{2}", soc), (t["occ_id"], soc)


def test_courses_v2_ids_are_real(esco_skill_uris):
    v1_ids = [r["course_id"] for r in rows("courses.csv")]
    extra_ids = [r["course_id"] for r in rows("courses_extra_v2.csv")]
    v2 = rows("courses_v2.csv")
    assert [r["id"] for r in v2] == v1_ids + extra_ids, "v2 keeps every v1 course (same order), then the added ones"
    for r in v2:
        uris = [u for u in r["esco_skill_uris"].split(";") if u]
        assert set(uris) <= esco_skill_uris, r["id"]
        assert all(not u.startswith("ESCO-") for u in uris)


def test_courses_v2_hours_verified_only_from_course_pages():
    for r in rows("courses_v2.csv"):
        if r["hours_verified"] == "true":
            assert r["url_kind"] == "course_page", r["id"]
            assert r["hours_method"], r["id"]
            assert float(r["hours"]) > 0
        else:
            assert r["hours_verified"] == "false"


def test_sdg_map_v2_covers_targets(occ_ids):
    sdg = rows("sdg_map_v2.csv")
    occ_rows = [r for r in sdg if r["key_type"] == "occupation"]
    assert {r["occ_id"] for r in occ_rows} == occ_ids
    for r in sdg:
        for g in filter(None, r["sdg_ids"].split(";")):
            assert 1 <= int(g) <= 17
        assert r["reason"]


def test_demand_masco_placeholders_hold_no_numbers():
    for r in rows("demand_masco_v2.csv"):
        assert 1 <= int(r["masco_major"]) <= 9
        if r["is_placeholder"] == "true":
            assert r["vacancies"] == "", "placeholder rows must stay empty"
        else:  # a real figure needs its source
            assert int(r["vacancies"]) >= 0
            assert r["source_url"].startswith("http")
            assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["source_date"])


def test_demand_occupation_map_matches_v1(occ_ids):
    v1 = [r["occupation"] for r in rows("malaysian_job_demand_real.csv")]
    m = rows("demand_occupation_map.csv")
    assert [r["demand_occupation"] for r in m] == v1
    for r in m:
        assert r["match_quality"] in {"exact", "approx", "none"}
        assert (r["occ_id"] == "") == (r["match_quality"] == "none")
        assert r["occ_id"] == "" or r["occ_id"] in occ_ids


def personas(name: str) -> dict:
    return json.loads((CURATED / name).read_text(encoding="utf-8-sig"))


def test_persona_maps_point_to_catalogue(occ_ids):
    v1 = personas("synthetic_personas.json")
    v1_ids = {p["id"] for k in v1 for p in v1[k]}
    for r in rows("persona_occupation_map.csv"):
        assert r["persona_id"] in v1_ids
        assert r["occ_id"] == "" or r["occ_id"] in occ_ids


def test_personas_v2_loader_compatible_and_private(occ_ids):
    data = personas("personas_v2.json")
    assert set(data) == {"individual_users", "hr_team_cohort"}
    loader_keys = {"id", "name", "persona_type", "current_role", "industry",
                   "experience_years", "current_skills", "cv_text"}
    for p in data["individual_users"]:
        assert loader_keys <= set(p)
        assert p["synthetic"] is True
        assert p["cv_text"].startswith("SYNTHETIC PERSONA")
    for group in data.values():
        for p in group:
            assert not FORBIDDEN_PERSONA_KEYS & {k.lower() for k in p}
            assert p["current_occ_id"] is None or p["current_occ_id"] in occ_ids
            text = json.dumps(p)
            assert not (NRIC.search(text) or EMAIL.search(text) or PHONE.search(text))
