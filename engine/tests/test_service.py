"""Engine facade: parse, match, radar, snapshots and diff on the real database."""
import pytest

from engine.parse import split_phrases, strip_pii

CV = """Accounts clerk.
- Maintain financial records and issue sales invoices.
- Follow up accounts receivables; reconcile bank statements.
- Use spreadsheets software. Age: 34, Gender: female. aina@example.com 012-345 6789
"""


def test_strip_pii_removes_age_gender_contact():
    clean = strip_pii(CV)
    for banned in ("34", "female", "aina@example.com", "6789"):
        assert banned not in clean


def test_split_phrases():
    ph = split_phrases(CV)
    assert "Maintain financial records and issue sales invoices" in ph
    assert "issue sales invoices" in ph


def test_parse_returns_db_skills_with_status(engine, store):
    found = engine.parse(CV)
    assert found, "expected matches"
    assert {f["skill_id"] for f in found} <= store.linked_skill_ids
    assert all(f["status"] in ("suggested", "needs_confirmation") for f in found)
    names = {f["skill_name"] for f in found}
    assert {"maintain financial records", "issue sales invoices"} <= names
    assert not any("34" in f["extracted_phrase"] or "female" in f["extracted_phrase"] for f in found)


def test_match_ranks_all_roles_but_current(engine, store):
    skills = [f["skill_id"] for f in engine.parse(CV)]
    r = engine.match(skills, current_occ="accounts_clerk")
    roles = r["roles"]
    assert r["label"] == "Estimate" and all(x["is_estimate"] for x in roles)
    assert {x["role_id"] for x in roles} == store.occupation_ids - {"accounts_clerk"}
    assert [x["rank"] for x in roles] == list(range(1, len(roles) + 1))
    assert sum(x["robustness"]["safest_pick"] for x in roles) == 1
    for x in roles:
        assert x["total_match_score"] == pytest.approx(sum(x["score_points"].values()), abs=0.25)
        assert x["source_badges"] and all(b["source"] and b["date"] for b in x["source_badges"])
        assert 0 <= x["robustness"]["top5_frequency"] <= 1


def test_match_without_current_occupation(engine, store):
    r = engine.match([], current_occ=None)
    assert len(r["roles"]) == len(store.occupation_ids)


def test_scenarios_and_snapshots(engine):
    with pytest.raises(KeyError):
        engine.gamma("instant")
    assert engine.resolve_snapshot("latest_snapshot") == engine.cfg["snapshots"]["latest"]
    with pytest.raises(KeyError):
        engine.resolve_snapshot("aei_1999")


def test_skill_signals_radar(engine):
    radar = engine.skill_signals(scenario="fast")
    assert radar and all(s["label"] == "Estimate" and s["source"]["date"] for s in radar)
    assert {s["status"] for s in radar} <= {"rising", "stable", "declining"}


def test_load_snapshot_switches_active(engine):
    out = engine.load_snapshot("latest_snapshot")
    assert out["active_snapshot_id"] == engine.cfg["snapshots"]["latest"]
    engine.load_snapshot("baseline_snapshot")


def test_diff_reports_rank_changes_with_driver(engine):
    skills = [f["skill_id"] for f in engine.parse(CV)]
    d = engine.diff(skills, current_occ="accounts_clerk")
    assert d["baseline_snapshot_id"] != d["new_snapshot_id"]
    assert d["changes"]
    for c in d["changes"]:
        assert c["movement"] == c["old_rank"] - c["new_rank"]
        assert c["driving_metric"] in ("outlook", "skill momentum")
        assert c["source"]["date"]


def test_personas_have_no_age_or_gender(engine):
    for p in engine.personas()["individual_users"]:
        assert not {"age", "gender"} & set(p)


def test_pathway_orders_steps_and_ranks_only_verified(engine, store):
    skills = [f["skill_id"] for f in engine.parse(CV)]
    p = engine.pathway(skills, "data_analyst", current_occ="accounts_clerk")
    assert p["missing_skills"] and set(p["missing_skills"]) <= store.skill_ids
    missing = set(p["missing_skills"])
    order = {k: i for i, k in enumerate(p["missing_skills"])}
    for k in p["missing_skills"]:                       # broader concepts come first
        for anc in engine._ancestors(k) & missing:
            assert order[anc] < order[k]
    for c in p["pathway"]:
        assert c["course_id"] in store.course_ids
        assert (c["marginal_score_per_hour"] is None) == (not c["hours_verified"])
    best = p["best_next_hour"]
    if best:
        assert best["hours_verified"] and best["marginal_score_per_hour"] == max(
            c["marginal_score_per_hour"] for c in p["pathway"] if c["marginal_score_per_hour"] is not None)
    with pytest.raises(KeyError):
        engine.pathway(skills, "astronaut")
