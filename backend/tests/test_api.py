from fastapi.testclient import TestClient

from backend.app.main import app


def test_p1_endpoints_are_gated_without_development_mode(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", False)
    client = TestClient(app)
    assert client.get("/api/signals").status_code == 503


def test_match_returns_ranked_estimates(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)
    response = client.post("/api/match", json={"skill_ids": ["skill-data-analysis"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "Estimate"
    assert payload["roles"][0]["total_match_score"] >= payload["roles"][1]["total_match_score"]
    assert all(role["is_estimate"] for role in payload["roles"])


def test_unknown_occupation_is_rejected(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)
    response = client.post(
        "/api/profile/parse",
        json={"occupation_id": "not-real", "text": "Excel"},
    )
    assert response.status_code == 422


def test_pathway_uses_verified_hours_only_and_marks_unverified(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)
    response = client.post(
        "/api/pathway",
        json={"skill_ids": [], "target_role_id": "role-project-support"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["label"] == "Estimate"
    assert payload["best_next_hour"]["hours_verified"] is True
    assert all(
        course["hours"] == "hours not verified"
        for course in payload["pathway"]
        if course["hours_verified"] is False
    )
    assert all(
        course["marginal_score_per_hour"] is None
        for course in payload["pathway"]
        if course["hours_verified"] is False
    )


def test_match_includes_1000_run_robustness_estimate(monkeypatch):
    from backend.app import config

    monkeypatch.setattr(config.settings, "dev_mode", True)
    client = TestClient(app)
    response = client.post("/api/match", json={"skill_ids": ["skill-data-analysis"]})
    assert response.status_code == 200
    robustness = response.json()["roles"][0]["robustness"]
    assert robustness["runs"] == 1000
    assert robustness["variation"] == 0.2
    assert robustness["label"] == "Estimate"
