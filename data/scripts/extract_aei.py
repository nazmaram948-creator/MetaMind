"""Extract task-level AI usage from Anthropic Economic Index releases into snapshots.

Snapshots (Claude.ai, global):
  aei_2025_11  release 2026-01-15, data 2025-11-13..2025-11-20 (long "raw" format,
               tasks keyed by lower-case task text)
  aei_2026_04  release 2026-06-26, data 2026-04 (tasks keyed by O*NET Task ID)
  aei_2026_05  release 2026-06-26, data 2026-05

Per task: usage_pct (share of all conversations, %), automation_pct and
augmentation_pct (share of the task's classified conversations, %). AEI's
buckets: automation = directive + feedback loop; augmentation = task iteration +
validation + learning. 'none' / 'not_classified' are excluded from the split.

Task text is joined to Task IDs through AEI's own task list
(release_2025_03_27/onet_task_statements.csv) and O*NET 31.0; IDs that are not
in O*NET 31.0 are dropped and written to aei_join_log.csv.

Writes data/extracts/aei_task_signals.csv, aei_country_signals.csv,
       aei_join_log.csv, aei_snapshots.json
Usage:  python data/scripts/extract_aei.py
"""
from __future__ import annotations

import json
import re

import pandas as pd

from _common import EXTRACTS, RAW, load_manifest

AEI = RAW / "aei"
HF = "https://huggingface.co/datasets/Anthropic/EconomicIndex"
V4_FILE = "release_2026_01_15/data/intermediate/aei_raw_claude_ai_2025-11-13_to_2025-11-20.csv"
V6_FILE = "release_2026_06_26/data/aei_claude_ai_2026-06-26.csv"
AUTOMATION = {"directive", "feedback loop"}
AUGMENTATION = {"task iteration", "validation", "learning"}

SNAPSHOTS = {
    "aei_2025_11": {"label": "AEI Nov 2025", "release": "2026-01-15", "period": "2025-11-13 to 2025-11-20",
                    "source_date": "2026-01-15", "file": V4_FILE},
    "aei_2026_04": {"label": "AEI Apr 2026", "release": "2026-06-26", "period": "2026-04-01 to 2026-05-01",
                    "source_date": "2026-06-26", "file": V6_FILE},
    "aei_2026_05": {"label": "AEI May 2026", "release": "2026-06-26", "period": "2026-05-01 to 2026-06-01",
                    "source_date": "2026-06-26", "file": V6_FILE},
}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def text_to_ids(ids31: set[int]) -> dict[str, set[int]]:
    """Map normalised task text -> O*NET 31.0 Task IDs (via 31.0 text and AEI's list)."""
    m: dict[str, set[int]] = {}
    ts31 = pd.read_csv(RAW / "onet" / "task_statements.csv")
    old = pd.read_csv(AEI / "release_2025_03_27" / "onet_task_statements.csv")
    for df in (ts31, old):
        for text, tid in zip(df["Task"].map(norm), df["Task ID"].astype(int)):
            if tid in ids31:
                m.setdefault(text, set()).add(tid)
    return m


def v4_snapshot(ids31: set[int], log: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(AEI / V4_FILE)
    g = raw[raw.geo_id == "GLOBAL"]
    usage = g[(g.facet == "onet_task") & (g.variable == "onet_task_pct")]
    usage = usage[~usage.cluster_name.isin(["none", "not_classified"])][["cluster_name", "value"]]

    collab = g[(g.facet == "onet_task::collaboration") & (g.variable == "onet_task_collaboration_pct")].copy()
    collab[["task", "pattern"]] = collab.cluster_name.str.rsplit("::", n=1, expand=True)
    collab["bucket"] = collab.pattern.map(lambda p: "auto" if p in AUTOMATION else "aug" if p in AUGMENTATION else None)
    split = collab.dropna(subset=["bucket"]).pivot_table(index="task", columns="bucket", values="value", aggfunc="sum")
    split = split.reindex(columns=["auto", "aug"]).fillna(0.0)
    total = split.auto + split.aug
    split = split[total > 0]
    split = pd.DataFrame({"automation_pct": 100 * split.auto / total[total > 0],
                          "augmentation_pct": 100 * split.aug / total[total > 0]})

    mapping = text_to_ids(ids31)
    rows = []
    for text, value in zip(usage.cluster_name, usage.value):
        ids = mapping.get(norm(text))
        if not ids:
            log.append({"snapshot_id": "aei_2025_11", "task_text": text, "reason": "no O*NET 31.0 Task ID for this text"})
            continue
        auto = split.automation_pct.get(text)
        aug = split.augmentation_pct.get(text)
        for tid in sorted(ids):
            rows.append({"snapshot_id": "aei_2025_11", "task_id": tid, "usage_pct": value,
                         "automation_pct": auto, "augmentation_pct": aug})
    tasks = pd.DataFrame(rows)

    # Malaysia vs global context (country facets in the raw file use 2-letter codes)
    ctx = []
    for geo, code in (("GLOBAL", "GLOBAL"), ("MY", "MYS")):
        sub = raw[raw.geo_id == geo]
        for var in ("usage_pct", "usage_per_capita_index"):
            v = sub[sub.variable == var].value
            if len(v):
                ctx.append({"snapshot_id": "aei_2025_11", "geo_id": code, "metric": var, "value": float(v.iloc[0])})
        c = sub[(sub.facet == "collaboration") & (sub.variable == "collaboration_pct")]
        c = c.set_index("cluster_name").value
        a, b = c.reindex(list(AUTOMATION)).sum(), c.reindex(list(AUGMENTATION)).sum()
        if a + b > 0:
            ctx.append({"snapshot_id": "aei_2025_11", "geo_id": code,
                        "metric": "collaboration_bucket_automation_pct", "value": 100 * a / (a + b)})
    return tasks, pd.DataFrame(ctx)


def v6_snapshots(ids31: set[int], log: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(AEI / V6_FILE, dtype={"node_external_id": str})
    tasks_all, ctx = [], []
    for sid, month in (("aei_2026_04", "2026-04-01"), ("aei_2026_05", "2026-05-01")):
        m = raw[raw.date_start == month]
        t = m[(m.category_name == "onet") & (m.hierarchy_level == 0) & (m.geo_id == "GLOBAL")]
        t = t[t.metric_id.isin(["pct", "collaboration_bucket_automation_pct", "collaboration_bucket_augmentation_pct"])]
        p = t.pivot_table(index="node_external_id", columns="metric_id", values="value", aggfunc="first")
        p = p.rename(columns={"pct": "usage_pct", "collaboration_bucket_automation_pct": "automation_pct",
                              "collaboration_bucket_augmentation_pct": "augmentation_pct"})
        p.index = pd.to_numeric(p.index, errors="coerce")
        for tid in p.index[p.index.isna() | ~p.index.isin(ids31)]:
            log.append({"snapshot_id": sid, "task_text": f"Task ID {tid}", "reason": "Task ID not in O*NET 31.0"})
        p = p[p.index.notna() & p.index.isin(ids31)].reset_index(names="task_id")
        p["task_id"] = p.task_id.astype(int)
        p.insert(0, "snapshot_id", sid)
        tasks_all.append(p[["snapshot_id", "task_id", "usage_pct", "automation_pct", "augmentation_pct"]])

        o = m[(m.category_name == "overall") & m.geo_id.isin(["GLOBAL", "MYS"])]
        o = o[o.metric_id.isin(["usage_pct", "usage_per_capita_index", "collaboration_bucket_automation_pct"])]
        for geo, metric, value in zip(o.geo_id, o.metric_id, o.value):
            ctx.append({"snapshot_id": sid, "geo_id": geo, "metric": metric, "value": float(value)})
    return pd.concat(tasks_all, ignore_index=True), pd.DataFrame(ctx)


def main() -> None:
    ids31 = set(pd.read_csv(RAW / "onet" / "task_statements.csv")["Task ID"].astype(int))
    log: list[dict] = []
    t4, c4 = v4_snapshot(ids31, log)
    t6, c6 = v6_snapshots(ids31, log)
    tasks = pd.concat([t4, t6], ignore_index=True)
    tasks = tasks.drop_duplicates(["snapshot_id", "task_id"])
    ctx = pd.concat([c4, c6], ignore_index=True).drop_duplicates(["snapshot_id", "geo_id", "metric"])

    EXTRACTS.mkdir(parents=True, exist_ok=True)
    tasks.round(4).to_csv(EXTRACTS / "aei_task_signals.csv", index=False)
    ctx.round(4).to_csv(EXTRACTS / "aei_country_signals.csv", index=False)
    pd.DataFrame(log, columns=["snapshot_id", "task_text", "reason"]).to_csv(EXTRACTS / "aei_join_log.csv", index=False)

    manifest = load_manifest()
    meta = {}
    for sid, s in SNAPSHOTS.items():
        meta[sid] = {**s, "source": "Anthropic Economic Index (Claude.ai, global)",
                     "source_url": f"{HF}/blob/main/{s['file']}", "licence": "CC-BY",
                     "fetched_at": manifest.get(f"data/raw/aei/{s['file']}", {}).get("fetched_at")}
    (EXTRACTS / "aei_snapshots.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    for sid, g in tasks.groupby("snapshot_id"):
        print(f"{sid}: {len(g)} tasks, usage sum {g.usage_pct.sum():.1f}%, "
              f"with automation split {g.automation_pct.notna().sum()}")
    print(f"dropped (logged): {len(log)}; country rows: {len(ctx)}")


if __name__ == "__main__":
    main()
