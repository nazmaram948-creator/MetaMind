"""Build the SQLite database from committed extracts + curated files.

    python -m engine.build            # uses engine/config.yaml (curated_version)
    CURATED_VERSION=v1 python -m engine.build

No network and no raw downloads are needed: everything comes from data/extracts/
and data/curated/. The build is deterministic and takes a few seconds.

Tables: meta, snapshots, occupations, skills, skill_broader, occ_skill, tasks,
occ_task, signals, courses, sdg_map.
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import CURATED, EXTRACTS, db_path, load_config

AEI_SOURCE = "Anthropic Economic Index (Claude.ai, global)"


def _read(path: Path, **kw) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, **kw)


def occupations() -> pd.DataFrame:
    t = _read(CURATED / "target_occupations.csv")
    esco = _read(EXTRACTS / "esco_occupations.csv").rename(columns={"uri": "esco_uri", "preferred_label": "esco_label"})
    out = t.merge(esco[["esco_uri", "esco_label", "description"]], on="esco_uri", how="left")
    if out.esco_label.eq("").any() or out.esco_label.isna().any():
        raise SystemExit("target occupation without ESCO record in extracts")
    out["masco_major"] = out.masco_major.astype(int)
    return out


def skills() -> pd.DataFrame:
    s = _read(EXTRACTS / "esco_skills.csv").rename(columns={"uri": "skill_uri", "preferred_label": "label"})
    for c in ("is_green", "is_digital", "is_transversal"):
        s[c] = s[c].astype(int)
    return s


def occ_skill(occ: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rel = _read(EXTRACTS / "esco_occ_skill.csv")
    rel = rel.merge(occ[["occ_id", "esco_uri"]], left_on="occupation_uri", right_on="esco_uri")
    w = {"essential": cfg["momentum"]["essential_weight"], "optional": cfg["momentum"]["optional_weight"]}
    rel["r"] = rel.relation.map(w)
    return rel[["occ_id", "skill_uri", "relation", "r"]].drop_duplicates(["occ_id", "skill_uri"])


def tasks_and_weights(occ: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = pd.read_csv(EXTRACTS / "onet_tasks.csv")
    rows = []
    for o in occ.itertuples():
        socs = o.onet_soc.split(";")
        for soc in socs:
            st = t[t.onet_soc == soc].copy()
            if st.importance.notna().any():
                basis = st.importance.notna().map({True: "O*NET importance (IM)", False: "IM imputed (occupation mean)"})
                st["w"] = st.importance.fillna(st.importance.mean())
            else:
                basis = pd.Series("equal (no IM ratings in O*NET 31.0)", index=st.index)
                st["w"] = 1.0
            st["w"] = st.w / st.w.sum() / len(socs)  # equal share per O*NET code
            for tid, w, b in zip(st.task_id, st.w, basis):
                rows.append({"occ_id": o.occ_id, "task_id": int(tid), "weight": float(w), "weight_basis": b})
    ot = pd.DataFrame(rows).groupby(["occ_id", "task_id"], as_index=False).agg(
        weight=("weight", "sum"), weight_basis=("weight_basis", "first"))
    tasks = t.drop_duplicates("task_id")[["task_id", "onet_soc", "onet_title", "task", "task_type",
                                          "importance", "importance_n", "importance_suppressed"]]
    return tasks, ot


def signals(cfg: dict, snaps: dict, built_at: str) -> pd.DataFrame:
    rows = []
    ts = pd.read_csv(EXTRACTS / "aei_task_signals.csv")
    for sid, g in ts.groupby("snapshot_id"):
        s = snaps[sid]
        for metric, col in (("usage_share", "usage_pct"), ("automation_share", "automation_pct"),
                            ("augmentation_share", "augmentation_pct")):
            v = g[["task_id", col]].dropna()
            rows.append(pd.DataFrame({
                "entity_type": "task", "entity_id": v.task_id.astype(str), "metric": metric,
                "value": v[col] / 100.0, "scenario": "", "period": s["period"], "source": AEI_SOURCE,
                "source_url": s["source_url"], "source_date": s["source_date"], "snapshot_id": sid,
                "verified": 1, "fetched_at": s.get("fetched_at") or built_at}))
    cs = pd.read_csv(EXTRACTS / "aei_country_signals.csv")
    for r in cs.itertuples():
        s = snaps[r.snapshot_id]
        rows.append(pd.DataFrame([{
            "entity_type": "country", "entity_id": r.geo_id, "metric": r.metric, "value": r.value,
            "scenario": "", "period": s["period"], "source": AEI_SOURCE, "source_url": s["source_url"],
            "source_date": s["source_date"], "snapshot_id": r.snapshot_id, "verified": 1,
            "fetched_at": s.get("fetched_at") or built_at}]))

    if cfg["curated_version"] == "v2":
        d = _read(CURATED / "demand_masco_v2.csv")
        d = d[d.vacancies != ""]
        if len(d):
            rows.append(pd.DataFrame({
                "entity_type": "masco_major", "entity_id": d.masco_major, "metric": "vacancies",
                "value": d.vacancies.astype(float), "scenario": "", "period": d.period, "source": d.source,
                "source_url": d.source_url, "source_date": d.source_date, "snapshot_id": "",
                "verified": (d.is_placeholder != "true").astype(int), "fetched_at": built_at}))
    else:
        d = _read(CURATED / "malaysian_job_demand_real.csv")
        m = _read(CURATED / "demand_occupation_map.csv")
        d = d.merge(m, left_on="occupation", right_on="demand_occupation")
        d = d[d.occ_id != ""]
        rows.append(pd.DataFrame({
            "entity_type": "occupation", "entity_id": d.occ_id, "metric": "demand_growth_pct",
            "value": d.growth_rate_pct.astype(float), "scenario": "", "period": "2025->2026",
            "source": d.source + " (v1 team sheet, no source URL)", "source_url": "",
            "source_date": d.date_published, "snapshot_id": "", "verified": 0, "fetched_at": built_at}))
    return pd.concat(rows, ignore_index=True)


def courses(cfg: dict) -> pd.DataFrame:
    if cfg["curated_version"] == "v2":
        c = _read(CURATED / "courses_v2.csv").rename(columns={"id": "course_id"})
        c["hours"] = pd.to_numeric(c.hours, errors="coerce")
        c["hours_verified"] = c.hours_verified.eq("true").astype(int)
        return c[["course_id", "title", "provider", "url", "url_kind", "hours", "hours_verified",
                  "hours_method", "cost_myr", "hrd_claimable", "esco_skill_uris", "mapping_confidence",
                  "relevant_to_targets", "checked_on", "status", "notes"]]
    c = _read(CURATED / "courses.csv")
    return pd.DataFrame({
        "course_id": c.course_id, "title": c.course_title, "provider": c.provider, "url": c.url,
        "url_kind": "not_checked", "hours": pd.to_numeric(c.hours), "hours_verified": c.hours_verified.str.upper().eq("TRUE").astype(int),
        "hours_method": "v1 team sheet", "cost_myr": c.cost, "hrd_claimable": "unknown",
        # v1 skill codes (ESCO-DA-01 ...) are not ESCO identifiers, so they cannot be linked
        "esco_skill_uris": "", "mapping_confidence": "", "relevant_to_targets": "false",
        "checked_on": "", "status": "v1", "notes": "v1 skill_ids: " + c.skill_ids})


def sdg_map(cfg: dict) -> pd.DataFrame:
    if cfg["curated_version"] == "v2":
        frame = _read(CURATED / "sdg_map_v2.csv")
        if "source" not in frame:
            frame["source"] = "UN SDG / ESCO Mapping"
        else:
            frame["source"] = frame["source"].fillna("").replace("", "UN SDG / ESCO Mapping")
        if "date_published" not in frame:
            frame["date_published"] = "2026-10"
        else:
            frame["date_published"] = frame["date_published"].fillna("").replace("", "2026-10")
        occupations_frame = occupations()
        by_title = {
            "".join(str(value).casefold().split()): occ_id
            for occ_id, title in occupations_frame[["occ_id", "title"]].itertuples(index=False)
            for value in [title]
        }
        # keep a valid occ_id when the row has one; otherwise match the row's title
        valid = set(occupations_frame.occ_id)
        unmatched = (frame["key_type"] == "occupation") & ~frame["occ_id"].isin(valid)
        frame.loc[unmatched, "occ_id"] = frame.loc[unmatched, "key"].map(
            lambda value: by_title.get("".join(str(value).casefold().split()), ""))
        known = set(frame.loc[frame["key_type"] == "occupation", "occ_id"]) - {""}
        missing = occupations_frame[~occupations_frame.occ_id.isin(known)]
        fallback = pd.DataFrame({
            "key_type": "occupation",
            "key": missing.title,
            "occ_id": missing.occ_id,
            "isco_code": missing.isco_code,
            "esco_uri": missing.esco_uri,
            "sdg_ids": "8",
            "targets": "",
            "reason": "Fallback SDG 8 tag; no direct curated occupation row was supplied.",
            "evidence": "Requires data-team review before production use.",
            "basis": "fallback",
            "status": "needs_review",
            "source": "UN SDG / ESCO Mapping",
            "date_published": "2026-10",
        })
        return pd.concat([frame, fallback], ignore_index=True)
    s = _read(CURATED / "sdg_mapping.csv")
    return pd.DataFrame({"key_type": "job_title", "key": s.occupation, "occ_id": "", "isco_code": "",
                         "esco_uri": "", "sdg_ids": s.sdg_link.str.extract(r"SDG (\d+)")[0], "targets": "",
                         "reason": s.reasoning, "evidence": "", "basis": "v1 team sheet", "status": "v1"})


def build(path: Path | None = None) -> Path:
    cfg = load_config()
    path = Path(path or db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    snaps = json.loads((EXTRACTS / "aei_snapshots.json").read_text(encoding="utf-8"))

    occ = occupations()
    tables = {
        "snapshots": pd.DataFrame([{"snapshot_id": k, **v} for k, v in snaps.items()]),
        "occupations": occ,
        "skills": skills(),
        "skill_broader": _read(EXTRACTS / "esco_skill_broader.csv"),
        "occ_skill": occ_skill(occ, cfg),
        "signals": signals(cfg, snaps, built_at),
        "courses": courses(cfg),
        "sdg_map": sdg_map(cfg),
    }
    tables["tasks"], tables["occ_task"] = tasks_and_weights(occ)
    meta = {
        "curated_version": cfg["curated_version"], "built_at": built_at,
        "esco": (EXTRACTS / "esco_meta.json").read_text(encoding="utf-8"),
        "onet": (EXTRACTS / "onet_meta.json").read_text(encoding="utf-8"),
    }

    tmp = path.with_name(f"{path.stem}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    with closing(sqlite3.connect(tmp)) as con, con:  # close: Windows keeps the file locked
        for name, df in tables.items():
            df.to_sql(name, con, index=False)
        pd.DataFrame({"key": list(meta), "value": list(meta.values())}).to_sql("meta", con, index=False)
        con.executescript("""
            CREATE UNIQUE INDEX ix_occ ON occupations(occ_id);
            CREATE UNIQUE INDEX ix_skill ON skills(skill_uri);
            CREATE INDEX ix_occ_skill ON occ_skill(occ_id);
            CREATE UNIQUE INDEX ix_task ON tasks(task_id);
            CREATE INDEX ix_occ_task ON occ_task(occ_id);
            CREATE INDEX ix_signals ON signals(entity_type, metric, snapshot_id);
            CREATE UNIQUE INDEX ix_course ON courses(course_id);
        """)
    tmp.replace(path)
    return path


def main() -> None:
    p = build(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    with closing(sqlite3.connect(p)) as con:
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    print(f"built {p} ({load_config()['curated_version']}): " + ", ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
