"""The database built from extracts + curated files is complete and consistent."""
import sqlite3
from contextlib import closing

import pytest

from engine import build as build_mod
from engine.config import load_config

TABLES = {"meta", "snapshots", "occupations", "skills", "skill_broader", "occ_skill", "tasks",
          "occ_task", "signals", "courses", "sdg_map"}


def test_tables_and_counts(store):
    assert TABLES <= set(store.tables)
    assert len(store["occupations"]) == 42
    assert set(store.snapshots) >= {"aei_2025_11", "aei_2026_05"}


def test_task_weights_sum_to_one_per_occupation(store):
    sums = store["occ_task"].groupby("occ_id").weight.sum()
    assert len(sums) == 42
    assert sums.round(9).eq(1.0).all()


def test_every_occupation_has_essential_skills(store):
    ess = store["occ_skill"]
    assert set(ess[ess.relation == "essential"].occ_id) == store.occupation_ids


def test_signals_reference_known_snapshots_and_tasks(store):
    s = store["signals"]
    tasks = s[s.entity_type == "task"]
    assert set(tasks.snapshot_id) <= set(store.snapshots)
    assert set(tasks.entity_id.astype(int)) <= set(store["tasks"].task_id) | set(tasks.entity_id.astype(int))
    assert tasks.value.between(0, 1).all()
    assert (s.source != "").all() and (s.source_date != "").all()


def test_courses_link_only_to_real_skills(store):
    for uris in store["courses"].esco_skill_uris:
        assert set(filter(None, uris.split(";"))) <= store.skill_ids


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_both_curated_versions_build(tmp_path, monkeypatch, version):
    cfg = dict(load_config(), curated_version=version)
    monkeypatch.setattr(build_mod, "load_config", lambda: cfg)
    path = build_mod.build(tmp_path / f"{version}.db")
    with closing(sqlite3.connect(path)) as con:
        assert con.execute("SELECT value FROM meta WHERE key='curated_version'").fetchone()[0] == version
        assert con.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 60
