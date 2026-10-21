from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.curated_data import (
    load_courses,
    load_demand_signals,
    load_personas,
    load_sdg_mappings,
)


def test_curated_files_have_expected_counts_and_types():
    courses = load_courses()
    demand = load_demand_signals()
    sdg = load_sdg_mappings()
    individuals, hr_cohort = load_personas()

    assert len(courses) == 60
    assert sum(course.hours_verified for course in courses) == 56
    assert len(demand) == 20
    assert len(sdg) == 40
    assert len(individuals) == 3
    assert len(hr_cohort) == 5
    assert individuals[1].id == "USR-002"
    assert individuals[1].current_role is None
    assert all(len(course.skill_ids) >= 1 for course in courses)


def test_curated_endpoints_expose_citations_sdg_and_personas(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)

    signals = client.get("/api/signals").json()
    assert len(signals) == 20
    assert signals[0]["source"]["source"]
    assert signals[0]["source"]["date"] == "2024-09-30"
    assert signals[0]["growth_rate_pct"] == 9.0

    mappings = client.get("/api/sdg").json()
    assert len(mappings) == 40
    assert mappings[0]["sdg_link"]
    assert mappings[0]["reasoning"]

    personas = client.get("/api/personas").json()
    assert len(personas["individual_users"]) == 3
    assert personas["individual_users"][1]["current_role"] is None
    assert len(personas["hr_team_cohort"]) == 5


def test_curated_courses_drive_pathway_and_verified_hours(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)
    response = client.post(
        "/api/pathway",
        json={"skill_ids": [], "target_role_id": "role-data-analyst"},
    )
    assert response.status_code == 200
    courses = response.json()["pathway"]
    assert courses
    assert all(course["course_id"].startswith("CRS-") for course in courses)
    assert all(isinstance(course["cost"], int) for course in courses)
    assert all(
        course["hours"] != "hours not verified"
        for course in courses
        if course["hours_verified"] is True
    )


def test_all_individual_personas_run_through_profile_and_pathway(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)
    individuals, _ = load_personas()

    for persona in individuals:
        parsed = client.post(
            "/api/profile/parse",
            json={"occupation_id": None, "text": persona.cv_text},
        )
        assert parsed.status_code == 200, persona.id
        skill_ids = [skill["skill_id"] for skill in parsed.json()["skills"]]
        pathway = client.post(
            "/api/pathway",
            json={"skill_ids": skill_ids, "target_role_id": "role-data-analyst"},
        )
        assert pathway.status_code == 200, persona.id
        assert pathway.json()["target_role_id"] == "role-data-analyst"
