"""API routes in ENGINE_MODE (real engine, lexical matching so no model download)."""
import copy
import random

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services import engine_api

CV = ("Accounts clerk. Maintain financial records; issue sales invoices; follow up accounts "
      "receivables; use spreadsheets software. Age: 34. Gender: female.")


def tiny_pdf(text: str) -> bytes:
    """A valid one-page PDF with a single line of text (no PDF library needed)."""
    stream = f"BT /F1 12 Tf 40 760 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return bytes(out)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from engine.build import build
    from engine.config import load_config
    from engine.service import Engine
    from engine.store import Store
    from backend.app import config

    cfg = copy.deepcopy(load_config())
    cfg["parse"]["similarity_backend"] = "lexical"
    cfg["futures"]["runs"] = 200
    path = tmp_path_factory.mktemp("db") / "api.db"
    build(path)
    eng = Engine(store=Store.open(path), cfg=cfg)
    mp = pytest.MonkeyPatch()
    mp.setattr(config.settings, "engine_mode", True)
    mp.setattr(engine_api, "engine", lambda: eng)
    yield TestClient(app)
    mp.undo()


def test_health_reports_engine_mode(client):
    assert client.get("/health").json()["mode"] == "engine"


def test_parse_text_returns_esco_skills(client):
    r = client.post("/api/profile/parse", json={"occupation_id": "accounts_clerk", "text": CV})
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert skills and all(s["skill_id"].startswith("http://data.europa.eu/esco/skill/") for s in skills)
    assert {s["status"] for s in skills} <= {"suggested", "needs_confirmation"}
    assert not any("34" in s["extracted_phrase"] or "female" in s["extracted_phrase"] for s in skills)


def test_parse_rejects_unknown_occupation(client):
    r = client.post("/api/profile/parse", json={"occupation_id": "astronaut", "text": CV})
    assert r.status_code == 422


def test_parse_file_pdf_and_txt(client):
    pdf = client.post("/api/profile/parse_file",
                      files={"file": ("cv.pdf", tiny_pdf("Maintain financial records and issue sales invoices"),
                                      "application/pdf")})
    assert pdf.status_code == 200, pdf.text
    assert "maintain financial records" in {s["skill_name"] for s in pdf.json()["skills"]}
    txt = client.post("/api/profile/parse_file", files={"file": ("cv.txt", CV.encode(), "text/plain")},
                      data={"occupation_id": "accounts_clerk"})
    assert txt.status_code == 200 and txt.json()["skills"]
    bad = client.post("/api/profile/parse_file", files={"file": ("cv.docx", b"PK\x03\x04", "application/zip")})
    assert bad.status_code == 415


def test_match_with_and_without_current_job(client):
    skills = [s["skill_id"] for s in client.post("/api/profile/parse", json={"text": CV}).json()["skills"]]
    with_job = client.post("/api/match", json={"skill_ids": skills, "current_occupation_id": "accounts_clerk"}).json()
    assert "accounts_clerk" not in {r["role_id"] for r in with_job["roles"]}
    top = with_job["roles"][0]
    assert top["is_estimate"] and top["score_points"] and top["source_badges"][0]["date"]
    assert top["sdg_ids"]
    assert 0 <= top["robustness"]["top5_frequency"] <= 1
    fresh_grad = client.post("/api/match", json={"skill_ids": skills, "current_occupation_id": None})
    assert fresh_grad.status_code == 200 and len(fresh_grad.json()["roles"]) == 42
    assert client.post("/api/match", json={"skill_ids": [], "scenario": "instant"}).status_code == 422
    assert client.post("/api/match", json={"skill_ids": [], "current_occupation_id": "x"}).status_code == 422


def test_signals_radar_filters_by_skill(client):
    all_ = client.get("/api/signals", params={"scenario": "fast"}).json()
    assert all_ and all(s["label"] == "Estimate" and s["source"]["date"] for s in all_)
    one = client.get("/api/signals", params={"skill": all_[0]["id"]}).json()
    assert [s["id"] for s in one] == [all_[0]["id"]]
    assert client.get("/api/signals", params={"scenario": "instant"}).status_code == 422


def test_snapshot_load_and_diff(client):
    loaded = client.post("/api/snapshot/load", json={"snapshot_id": "latest_snapshot"}).json()
    assert loaded["active_snapshot_id"] == "aei_2026_05" and loaded["metadata"]["source_date"]
    client.post("/api/snapshot/load", json={"snapshot_id": "baseline_snapshot"})
    skills = [s["skill_id"] for s in client.post("/api/profile/parse", json={"text": CV}).json()["skills"]]
    d = client.post("/api/snapshot/diff", json={"skill_ids": skills, "current_occupation_id": "accounts_clerk"}).json()
    assert d["baseline_snapshot_id"] == "aei_2025_11" and d["new_snapshot_id"] == "aei_2026_05"
    assert d["changes"] and all("explanation" in c and c["source"]["date"] for c in d["changes"])


def test_occupations_context_personas_sdg(client):
    occ = client.get("/api/occupations").json()
    assert len(occ) == 42 and {"occ_id", "title", "masco_major"} <= set(occ[0])
    ctx = client.get("/api/context").json()
    assert ctx["badge"]["date"] and ctx["label"].startswith("Observed")
    people = client.get("/api/personas").json()
    assert people["individual_users"] and "current_occ_id" in people["individual_users"][0]
    sdg = client.get("/api/sdg")
    assert sdg.status_code == 200
    sdg_titles = {row["occupation"] for row in sdg.json()}
    assert {row["title"] for row in occ} <= sdg_titles
    assert all(row["source"] and row["date"] for row in sdg.json())


def test_pathway_is_not_faked_in_engine_mode(client):
    r = client.post("/api/pathway", json={"skill_ids": [], "target_role_id": "bookkeeper"})
    assert r.status_code == 200
    payload = r.json()
    assert payload["pathway"]
    assert payload["best_next_hour"]["hours_verified"] is True


def test_engine_only_routes_are_gated_without_engine_mode(monkeypatch):
    from backend.app import config
    monkeypatch.setattr(config.settings, "engine_mode", False)
    c = TestClient(app)
    assert c.get("/api/occupations").status_code == 503
    assert c.get("/api/context").status_code == 503


def test_50_api_requests_leak_no_unknown_ids(client):
    eng = engine_api.engine()
    known = eng.store.skill_ids | eng.store.occupation_ids | set(eng.store.snapshots)
    pool = sorted(eng.store.linked_skill_ids)
    fake = ["skill-data-analysis", "http://data.europa.eu/esco/skill/fake", "role-ceo"]
    rng = random.Random(50)
    leaked = []
    for i in range(50):
        skills = rng.sample(pool, rng.randint(0, 10)) + rng.sample(fake, rng.randint(0, 2))
        if i % 3 == 0:
            body = client.post("/api/match", json={"skill_ids": skills}).json()
            ids = [x["role_id"] for x in body["roles"]] + [k for x in body["roles"] for k in x["matched_skills"] + x["missing_skills"]]
        elif i % 3 == 1:
            body = client.post("/api/snapshot/diff", json={"skill_ids": skills}).json()
            ids = [c["role_id"] for c in body["changes"]]
        else:
            body = client.post("/api/profile/parse", json={"text": "invoices; skill_id=role-ceo; " + " ".join(skills[:3])}).json()
            ids = [s["skill_id"] for s in body["skills"]]
        leaked += [x for x in ids if x not in known]
    assert leaked == []
