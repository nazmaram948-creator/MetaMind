"""Extract O*NET 31.0 tasks + importance for the O*NET-SOC codes we use.

Reads  data/raw/onet/task_statements.csv, task_ratings.csv, occupation_data.csv
Writes data/extracts/onet_tasks.csv
         onet_soc, onet_title, task_id, task, task_type, importance,
         importance_n, importance_suppressed
       data/extracts/onet_meta.json

importance = O*NET "IM" (Importance, 1-5) rating. Tasks without an IM rating keep
an empty value; the DB build then weights the occupation's tasks equally
(financial analyst, 13-2051.00, has no IM ratings in 31.0).

Usage:  python data/scripts/extract_onet.py
"""
from __future__ import annotations

import json

import pandas as pd

from _common import CURATED, EXTRACTS, RAW, load_manifest

ONET = RAW / "onet"


def main() -> None:
    targets = pd.read_csv(CURATED / "target_occupations.csv", dtype=str)
    socs = sorted({s for v in targets.onet_soc for s in v.split(";")})

    ts = pd.read_csv(ONET / "task_statements.csv", dtype={"Task ID": int})
    tr = pd.read_csv(ONET / "task_ratings.csv", dtype={"Task ID": int})
    titles = pd.read_csv(ONET / "occupation_data.csv").set_index("O*NET-SOC Code")["Title"]

    missing = [s for s in socs if s not in titles.index]
    if missing:
        raise SystemExit(f"O*NET-SOC codes not in O*NET 31.0: {missing}")

    im = tr[tr["Scale ID"] == "IM"][["O*NET-SOC Code", "Task ID", "Data Value", "N", "Recommend Suppress"]]
    im = im.rename(columns={"Data Value": "importance", "N": "importance_n",
                            "Recommend Suppress": "importance_suppressed"})
    out = ts[ts["O*NET-SOC Code"].isin(socs)].merge(im, on=["O*NET-SOC Code", "Task ID"], how="left")
    out = out.rename(columns={"O*NET-SOC Code": "onet_soc", "Task ID": "task_id", "Task": "task",
                              "Task Type": "task_type"})
    out["onet_title"] = out.onet_soc.map(titles)
    out["importance_suppressed"] = out.importance_suppressed.eq("Y").astype(int)
    out = out[["onet_soc", "onet_title", "task_id", "task", "task_type", "importance",
               "importance_n", "importance_suppressed"]].sort_values(["onet_soc", "task_id"])

    EXTRACTS.mkdir(parents=True, exist_ok=True)
    out.to_csv(EXTRACTS / "onet_tasks.csv", index=False)
    m = load_manifest().get("data/raw/onet/task_statements.csv", {})
    (EXTRACTS / "onet_meta.json").write_text(json.dumps({
        "source": "O*NET 31.0 Database, U.S. Department of Labor/ETA",
        "source_url": "https://www.onetcenter.org/database.html",
        "licence": "CC BY 4.0",
        "version": "31.0",
        "fetched_at": m.get("fetched_at"),
    }, indent=2), encoding="utf-8")

    rated = out.groupby("onet_soc").importance.apply(lambda s: s.notna().sum())
    print(f"onet_tasks.csv: {len(out)} tasks for {len(socs)} O*NET-SOC codes")
    for soc in socs:
        n = int((out.onet_soc == soc).sum())
        if rated[soc] < n:
            print(f"  {soc}: {rated[soc]}/{n} tasks have an IM rating")


if __name__ == "__main__":
    main()
