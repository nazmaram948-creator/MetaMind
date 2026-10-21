"""Read-only view of the SQLite database, loaded once into pandas frames."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import pandas as pd

from .build import build
from .config import db_path


@dataclass
class Store:
    path: Path
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)

    @classmethod
    def open(cls, path: Path | None = None, *, rebuild: bool = False) -> "Store":
        path = Path(path or db_path())
        if rebuild or not path.exists():
            build(path)
        with closing(sqlite3.connect(path)) as con:
            names = [n for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            tables = {n: pd.read_sql(f"SELECT * FROM {n}", con) for n in names}
        return cls(path=path, tables=tables)

    def __getitem__(self, name: str) -> pd.DataFrame:
        return self.tables[name]

    @cached_property
    def meta(self) -> dict[str, str]:
        return dict(zip(self["meta"].key, self["meta"].value))

    @cached_property
    def snapshots(self) -> dict[str, dict]:
        return {r["snapshot_id"]: r for r in self["snapshots"].to_dict("records")}

    @cached_property
    def occupation_ids(self) -> set[str]:
        return set(self["occupations"].occ_id)

    @cached_property
    def skill_ids(self) -> set[str]:
        return set(self["skills"].skill_uri)

    @cached_property
    def linked_skill_ids(self) -> set[str]:
        """Skills attached to at least one target occupation (the matchable pool)."""
        return set(self["occ_skill"].skill_uri)

    @cached_property
    def course_ids(self) -> set[str]:
        return set(self["courses"].course_id)

    @cached_property
    def skill_label(self) -> dict[str, str]:
        return dict(zip(self["skills"].skill_uri, self["skills"].label))

    @cached_property
    def occ_title(self) -> dict[str, str]:
        return dict(zip(self["occupations"].occ_id, self["occupations"].title))

    def task_signals(self, snapshot_id: str) -> pd.DataFrame:
        """task_id, usage_share, automation_share, augmentation_share for one snapshot."""
        s = self["signals"]
        s = s[(s.entity_type == "task") & (s.snapshot_id == snapshot_id)]
        p = s.pivot_table(index="entity_id", columns="metric", values="value", aggfunc="first")
        p.index = p.index.astype(int)
        return p.reindex(columns=["usage_share", "automation_share", "augmentation_share"])

    def country_signal(self, snapshot_id: str, geo: str, metric: str) -> float | None:
        s = self["signals"]
        v = s[(s.entity_type == "country") & (s.snapshot_id == snapshot_id)
              & (s.entity_id == geo) & (s.metric == metric)].value
        return float(v.iloc[0]) if len(v) else None

    def badge(self, snapshot_id: str) -> dict:
        s = self.snapshots[snapshot_id]
        return {"source": f"{s['source']}, {s['label']}", "date": s["source_date"],
                "url": s["source_url"], "period": s["period"]}

    def static_badges(self) -> list[dict]:
        esco = json.loads(self.meta["esco"])
        onet = json.loads(self.meta["onet"])
        return [{"source": esco["source"], "date": (esco.get("fetched_at") or "")[:10], "url": esco["source_url"]},
                {"source": onet["source"], "date": (onet.get("fetched_at") or "")[:10], "url": onet["source_url"]}]
