"""Engine facade used by the API: one object, cached per snapshot and scenario.

Every number it returns travels with a source badge {source, date} and every
ranking or forecast with label "Estimate". All responses pass validate_ids.
"""
from __future__ import annotations

import importlib.util
import json
import logging
from functools import lru_cache

import pandas as pd

from . import model
from .config import CURATED, load_config
from .guardrail import validate_ids
from .parse import parse as parse_text
from .similarity import Similarity
from .store import Store

log = logging.getLogger("skillshift.engine")
ESTIMATE = "Estimate"
ALIASES = {"baseline_snapshot": "baseline", "latest_snapshot": "latest"}


class Engine:
    def __init__(self, store: Store | None = None, cfg: dict | None = None):
        self.cfg = cfg or load_config()
        self.store = store or Store.open()
        self.active_snapshot = self.cfg["snapshots"]["baseline"]
        backend = self.cfg["parse"]["similarity_backend"]
        if backend == "minilm" and importlib.util.find_spec("sentence_transformers") is None:
            log.warning("sentence-transformers not installed: using lexical skill matching")
            backend = "lexical"
        self.similarity_backend = backend
        sk = self.store["skills"]
        alts = {u: [a for a in (s or "").split("|") if a] for u, s in zip(sk.skill_uri, sk.alt_labels)}
        self.sim = Similarity(dict(zip(sk.skill_uri, sk.label)), alts,
                              backend=backend, model_name=self.cfg["parse"]["model"])
        os_ = self.store["occ_skill"]
        ess = os_[os_.relation == "essential"]
        self.essentials = {o: sorted(g.skill_uri) for o, g in ess.groupby("occ_id")}
        self.candidates = sorted(self.store.linked_skill_ids)
        self._cache: dict = {}

    # ---------- helpers ----------
    def resolve_snapshot(self, snapshot_id: str | None) -> str:
        if not snapshot_id:
            return self.active_snapshot
        sid = self.cfg["snapshots"].get(ALIASES.get(snapshot_id, ""), snapshot_id)
        if sid not in self.store.snapshots:
            raise KeyError(f"unknown snapshot_id {snapshot_id!r}")
        return sid

    def gamma(self, scenario: str) -> float:
        presets = self.cfg["outlook"]["presets"]
        if scenario not in presets:
            raise KeyError(f"unknown scenario {scenario!r}; use one of {sorted(presets)}")
        return presets[scenario]["gamma"]

    def demand_z(self) -> tuple[pd.Series, list[dict]]:
        """D per occupation (z-scored) and the badges of the demand rows used."""
        if not self.cfg["outlook"]["use_unverified_demand"]:
            return pd.Series(dtype=float), []
        s = self.store["signals"]
        d = s[s.entity_type.isin(["occupation", "masco_major"])]
        if d.empty:
            return pd.Series(dtype=float), []
        occ = self.store["occupations"]
        if (d.entity_type == "occupation").any():
            g = d[d.metric == "demand_growth_pct"].groupby("entity_id").value.mean()
        else:  # vacancies by MASCO group and period -> growth between first and last period
            v = d.pivot_table(index="entity_id", columns="period", values="value")
            growth = (v[v.columns[-1]] / v[v.columns[0]] - 1).dropna()
            g = occ.set_index("occ_id").masco_major.astype(str).map(growth).dropna()
        badges = [{"source": r.source, "date": r.source_date} for r in d.drop_duplicates("source").itertuples()]
        return model.zscore(g), badges

    def state(self, snapshot_id: str, scenario: str) -> dict:
        key = (snapshot_id, scenario)
        if key not in self._cache:
            default_auto = (self.store.country_signal(snapshot_id, "GLOBAL", "collaboration_bucket_automation_pct")
                            or 50.0) / 100
            exp = model.exposure(self.store["occ_task"], self.store.task_signals(snapshot_id), default_auto)
            d, demand_badges = self.demand_z()
            o = model.outlook(exp, d, self.cfg["outlook"]["alpha"], self.cfg["outlook"]["beta"], self.gamma(scenario))
            m = model.momentum(self.store["occ_skill"], o.O)
            self._cache[key] = {"exp": exp, "outlook": o, "m": m, "demand_badges": demand_badges}
        return self._cache[key]

    def badges(self, snapshot_id: str, demand: list[dict] | None = None) -> list[dict]:
        out = [self.store.badge(snapshot_id), *self.store.static_badges()]
        return out + (demand or [])

    def _guard(self, payload):
        clean, _ = validate_ids(payload, self.store)
        return clean

    # ---------- API ----------
    def occupations(self) -> list[dict]:
        occ = self.store["occupations"]
        cols = ["occ_id", "title", "isco_code", "masco_major", "family", "role_type", "esco_label", "onet_soc"]
        return self._guard(occ[cols].to_dict("records"))

    def parse(self, text: str) -> list[dict]:
        p = self.cfg["parse"]
        found = parse_text(text, self.sim, self.candidates, auto_suggest=p["auto_suggest"],
                           min_candidate=p["min_candidate"], max_per_phrase=p["max_per_phrase"],
                           max_results=p["max_results"])
        return self._guard(found)

    def malaysia_context(self, snapshot_id: str | None = None) -> dict:
        sid = self.resolve_snapshot(snapshot_id)
        get = self.store.country_signal
        return {"snapshot_id": sid, "badge": self.store.badge(sid), "label": "Observed usage (not a forecast)",
                "malaysia_usage_index": get(sid, "MYS", "usage_per_capita_index"),
                "malaysia_usage_pct_of_global": get(sid, "MYS", "usage_pct"),
                "malaysia_automation_pct": get(sid, "MYS", "collaboration_bucket_automation_pct"),
                "global_automation_pct": get(sid, "GLOBAL", "collaboration_bucket_automation_pct")}

    def skill_signals(self, skill_ids: list[str] | None = None, scenario: str = "moderate",
                      snapshot_id: str | None = None, limit: int = 12) -> list[dict]:
        """Skills Radar: momentum M_k with rising / stable / declining."""
        sid = self.resolve_snapshot(snapshot_id)
        st = self.state(sid, scenario)
        m = st["m"]
        if skill_ids:
            ids = [k for k in skill_ids if k in m.index]
        else:  # strongest movers in the catalogue
            ids = list(m.sort_values(ascending=False).index[:limit]) + list(m.sort_values().index[:limit])
        thr = self.cfg["momentum"]["radar_threshold"]
        sk = self.store["skills"].set_index("skill_uri")
        badge = {"source": f"SkillShift estimate from {self.store.badge(sid)['source']}, O*NET 31.0, ESCO v1.2",
                 "date": self.store.badge(sid)["date"]}
        out = [{"id": k, "name": sk.label[k], "value": round(float(m[k]), 3),
                "status": model.radar_status(float(m[k]), thr), "is_green": bool(sk.is_green[k]),
                "is_digital": bool(sk.is_digital[k]), "scenario": scenario, "snapshot_id": sid,
                "label": ESTIMATE, "source": badge} for k in dict.fromkeys(ids)]
        return self._guard(out)

    def rank(self, skill_ids: list[str], current_occ: str | None, scenario: str, snapshot_id: str,
             sdg_preference: float | None = None) -> pd.DataFrame:
        st = self.state(snapshot_id, scenario)
        mc = self.cfg["match"]
        # SDG term (P3) stays at lambda = 0 until the SDG slider is built; sdg_preference is accepted but unused.
        lam = mc["sdg_lambda"]
        exclude = [current_occ] if (current_occ and mc["exclude_current"]) else []
        return model.match(skill_ids, self.essentials, st["outlook"].O_hat, st["m"], self.sim.skills,
                           weights=mc["weights"], kappa=mc["momentum_kappa"], sdg_lambda=lam, exclude=exclude,
                           normalise=mc["normalise_components"])

    def match(self, skill_ids: list[str], current_occ: str | None = None, scenario: str = "moderate",
              snapshot_id: str | None = None, sdg_preference: float | None = None) -> dict:
        sid = self.resolve_snapshot(snapshot_id)
        skill_ids = [k for k in dict.fromkeys(skill_ids) if k in self.store.skill_ids]
        st = self.state(sid, scenario)
        ranked = self.rank(skill_ids, current_occ, scenario, sid, sdg_preference)
        f = self.cfg["futures"]
        fut = model.futures(ranked, self.essentials, st["m"], skill_ids, weights=self.cfg["match"]["weights"],
                            kappa=self.cfg["match"]["momentum_kappa"], runs=f["runs"], r=f["momentum_noise_r"],
                            seed=f["seed"], top_n=f["top_n"],
                            normalise=self.cfg["match"]["normalise_components"]).set_index("occ_id")
        safest = fut.loc[ranked.occ_id[:10]].sort_values(["worst_rank", "p_top"], ascending=[True, False]).index[0]
        exp = st["exp"]
        badges = self.badges(sid, st["demand_badges"])
        roles = []
        for r in ranked.itertuples():
            fr = fut.loc[r.occ_id]
            auto = exp.automation_share.get(r.occ_id)
            roles.append({
                "role_id": r.occ_id, "role_title": self.store.occ_title[r.occ_id], "rank": int(r.rank),
                "total_match_score": round(r.S, 1),
                # what the user reads: raw shares / index on a 0-100 scale
                "score_breakdown": {"skills_covered_score": round(100 * r.C_raw, 1),
                                    "role_trend_score": round(100 * r.O_hat, 1),
                                    "transferability_score": round(100 * r.T_raw, 1),
                                    "sdg_score": round(r.SDG, 1)},
                # points each part adds to total_match_score (they sum to it)
                "score_points": {"coverage": round(r.pts_coverage, 1), "outlook": round(r.pts_outlook, 1),
                                 "transferability": round(r.pts_transferability, 1), "sdg": 0.0},
                "essential_skills_total": int(r.n_essential),
                "weights": self.cfg["match"]["weights"],
                "matched_skills": r.matched, "missing_skills": r.missing,
                "matched_skill_names": [self.store.skill_label[k] for k in r.matched],
                "missing_skill_names": [self.store.skill_label[k] for k in r.missing],
                "ai_exposure": {"automation_share_pct": None if pd.isna(auto) else round(100 * auto, 1),
                                "observed_task_weight_pct": round(100 * float(exp.observed_weight[r.occ_id]), 1),
                                "source": self.store.badge(sid)},
                "robustness_estimate": f"Estimate: stays in your top {f['top_n']} in {round(100 * fr.p_top)}% of "
                                       f"{f['runs']:,} simulated futures",
                "robustness": {"runs": f["runs"], "variation": f["momentum_noise_r"], "top5_frequency": round(float(fr.p_top), 4),
                               "median_score": round(float(fr["median"]), 1), "p10": round(float(fr.p10), 1),
                               "p90": round(float(fr.p90), 1), "worst_rank": int(fr.worst_rank),
                               "safest_pick": r.occ_id == safest, "label": ESTIMATE,
                               "assumption_note": f["assumption"]},
                "source_badges": badges, "is_estimate": True,
            })
        return self._guard({"roles": roles, "snapshot_id": sid, "scenario": scenario, "label": ESTIMATE,
                            "assumption_note": f["assumption"]})

    def load_snapshot(self, snapshot_id: str) -> dict:
        self.active_snapshot = self.resolve_snapshot(snapshot_id)
        s = self.store.snapshots[self.active_snapshot]
        return {"status": "loaded", "active_snapshot_id": self.active_snapshot,
                "metadata": {"label": s["label"], "source": s["source"], "source_date": s["source_date"],
                             "period": s["period"], "source_url": s["source_url"]}}

    def diff(self, skill_ids: list[str], current_occ: str | None = None, scenario: str = "moderate",
             baseline: str | None = None, new: str | None = None, top: int = 5) -> dict:
        a = self.resolve_snapshot(baseline or "baseline_snapshot")
        b = self.resolve_snapshot(new or "latest_snapshot")
        skill_ids = [k for k in dict.fromkeys(skill_ids) if k in self.store.skill_ids]
        ra = self.rank(skill_ids, current_occ, scenario, a).set_index("occ_id")
        rb = self.rank(skill_ids, current_occ, scenario, b).set_index("occ_id")
        ea, eb = self.state(a, scenario)["exp"], self.state(b, scenario)["exp"]
        la, lb = self.store.snapshots[a]["label"], self.store.snapshots[b]["label"]
        roles = list(dict.fromkeys(list(rb.index[rb["rank"] <= top]) + list(ra.index[ra["rank"] <= top])))
        changes = []
        for o in roles:
            d_out = rb.pts_outlook[o] - ra.pts_outlook[o]
            d_cov = rb.pts_coverage[o] - ra.pts_coverage[o]
            driver = "outlook" if abs(d_out) >= abs(d_cov) else "skill momentum"
            sa, sb = ea.automation_share.get(o), eb.automation_share.get(o)
            detail = ""
            if driver == "outlook" and pd.notna(sa) and pd.notna(sb):
                detail = (f"; AI automation share of its observed tasks {100 * sa:.0f}% -> {100 * sb:.0f}%, "
                          f"AI usage of its tasks x{(eb.E[o] / ea.E[o]) if ea.E[o] > 0 else float('nan'):.2f}")
            old, newr = int(ra["rank"][o]), int(rb["rank"][o])
            changes.append({
                "role_id": o, "role_title": self.store.occ_title[o], "old_rank": old, "new_rank": newr,
                "movement": old - newr, "old_score": round(float(ra.S[o]), 1), "new_score": round(float(rb.S[o]), 1),
                "driving_metric": driver,
                "explanation": f"Rank {old} -> {newr} ({la} -> {lb}). Main driver: {driver} "
                               f"(outlook {d_out:+.1f} pts, coverage {d_cov:+.1f} pts){detail}.",
                "source": self.store.badge(b), "label": ESTIMATE,
            })
        changes.sort(key=lambda c: c["new_rank"])
        return self._guard({"baseline_snapshot_id": a, "new_snapshot_id": b, "changes": changes,
                            "label": ESTIMATE, "assumption_note": self.cfg["futures"]["assumption"]})

    def personas(self) -> dict:
        name = "personas_v2.json" if self.cfg["curated_version"] == "v2" else "synthetic_personas.json"
        return json.loads((CURATED / name).read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return Engine()
