"""Engine facade used by the API: one object, cached per snapshot and scenario.

Every number it returns travels with a source badge {source, date} and every
ranking or forecast with label "Estimate". All responses pass validate_ids.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import re
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

    def sdg_strength(self) -> pd.Series:
        """SDG_o per occupation (0..1): how much of the role's ESCO skill profile carries SDG evidence.

        Skill evidence e_k: 1 if the skill is in ESCO's Green collection or is one of the role's
        skills mapped to an SDG target in sdg_map ("has '<label>'" in evidence); sdg_digital_weight
        if it is only in the Digital collection; else 0. SDG_o = sum(r_ok * e_k) / sum(r_ok), with
        r = 1 essential / 0.5 optional, divided by the maximum over roles.
        """
        if "sdg_strength" not in self._cache:
            sk = self.store["skills"].set_index("skill_uri")
            by_label = dict(zip(sk.label, sk.index))
            dw = self.cfg["match"]["sdg_digital_weight"]
            sm = self.store["sdg_map"]
            targets: dict[str, set[str]] = {}
            for occ, ev in zip(sm.occ_id.fillna(""), sm.evidence.fillna("")):
                if occ:
                    labels = re.findall(r"has '([^']+)'", str(ev))
                    targets.setdefault(occ, set()).update(by_label[x] for x in labels if x in by_label)
            share = {}
            for occ, g in self.store["occ_skill"].groupby("occ_id"):
                tgt = targets.get(occ, set())
                e = [1.0 if (sk.is_green.get(u, 0) or u in tgt) else dw if sk.is_digital.get(u, 0) else 0.0
                     for u in g.skill_uri]
                share[occ] = float((g.r.to_numpy() * e).sum() / g.r.sum()) if g.r.sum() else 0.0
            s = pd.Series(share)
            self._cache["sdg_strength"] = s / s.max() if s.max() > 0 else s
        return self._cache["sdg_strength"]

    def sdg_lambda(self, sdg_preference: float | None) -> float:
        mc = self.cfg["match"]
        if sdg_preference is None:
            return float(mc["sdg_lambda"])
        return float(mc["sdg_lambda_max"]) * min(max(float(sdg_preference), 0.0), 1.0)

    def rank(self, skill_ids: list[str], current_occ: str | None, scenario: str, snapshot_id: str,
             sdg_preference: float | None = None) -> pd.DataFrame:
        """S = 100 (wc C + wo O_hat + wt T) + lambda SDG_o; lambda comes from the SDG slider."""
        st = self.state(snapshot_id, scenario)
        mc = self.cfg["match"]
        exclude = [current_occ] if (current_occ and mc["exclude_current"]) else []
        return model.match(skill_ids, self.essentials, st["outlook"].O_hat, st["m"], self.sim.skills,
                           weights=mc["weights"], kappa=mc["momentum_kappa"], sdg=self.sdg_strength(),
                           sdg_lambda=self.sdg_lambda(sdg_preference), exclude=exclude,
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
                            seed=f["seed"], top_n=f["top_n"], sdg_lambda=self.sdg_lambda(sdg_preference),
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
                                    "sdg_score": round(100 * r.SDG, 1)},
                # points each part adds to total_match_score (they sum to it)
                "score_points": {"coverage": round(r.pts_coverage, 1), "outlook": round(r.pts_outlook, 1),
                                 "transferability": round(r.pts_transferability, 1),
                                 "sdg": round(float(r.pts_sdg), 1)},
                "essential_skills_total": int(r.n_essential),
                "weights": {**self.cfg["match"]["weights"], "sdg_lambda": self.sdg_lambda(sdg_preference)},
                "matched_skills": r.matched, "missing_skills": r.missing,
                "sdg_tags": [
                    f"SDG {value}" for value in str(
                        next(
                            (
                                row.sdg_ids for row in self.store["sdg_map"].itertuples()
                                if getattr(row, "occ_id", "") == r.occ_id
                            ),
                            "",
                        )
                    ).split(";") if value
                ],
                "sdg_ids": [
                    value for value in str(
                        next(
                            (
                                row.sdg_ids for row in self.store["sdg_map"].itertuples()
                                if getattr(row, "occ_id", "") == r.occ_id
                            ),
                            "",
                        )
                    ).split(";") if value
                ],
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

    # ---------- P2: learning pathway ----------
    def _courses_by_skill(self) -> dict[str, list[dict]]:
        if "courses_by_skill" not in self._cache:
            idx: dict[str, list[dict]] = {}
            for c in self.store["courses"].to_dict("records"):
                for uri in filter(None, (c["esco_skill_uris"] or "").split(";")):
                    idx.setdefault(uri, []).append(c)
            self._cache["courses_by_skill"] = idx
        return self._cache["courses_by_skill"]

    def _ancestors(self, uri: str) -> set[str]:
        """Broader ESCO concepts of a skill (skill pillar, all levels)."""
        key = ("anc", uri)
        if key not in self._cache:
            br = self._cache.setdefault("broader", {})
            if not br:
                for s, b in zip(self.store["skill_broader"].skill_uri, self.store["skill_broader"].broader_uri):
                    br.setdefault(s, set()).add(b)
            seen, todo = set(), [uri]
            while todo:
                for b in br.get(todo.pop(), ()):
                    if b not in seen:
                        seen.add(b)
                        todo.append(b)
            self._cache[key] = seen
        return self._cache[key]

    @staticmethod
    def _pick_course(courses: list[dict]) -> dict | None:
        """Shortest course with verified hours (then cheapest); else the cheapest unverified one."""
        cost = lambda c: int(c["cost_myr"]) if str(c["cost_myr"]).isdigit() else 10**9
        verified = [c for c in courses if c["hours_verified"] and pd.notna(c["hours"])]
        if verified:
            return min(verified, key=lambda c: (c["hours"], cost(c), c["course_id"]))
        return min(courses, key=lambda c: (cost(c), c["course_id"])) if courses else None

    def _sdg_tags(self, course: dict) -> list[str]:
        sk = self.store["skills"].set_index("skill_uri")
        goals: set[int] = set()
        for uri in filter(None, course["esco_skill_uris"].split(";")):
            if uri in sk.index:
                if sk.is_green[uri]:
                    goals |= {7, 12, 13}   # ESCO Green collection (project rule)
                if sk.is_digital[uri]:
                    goals.add(9)          # ESCO Digital collection
        return [f"SDG {g}" for g in sorted(goals)]

    def pathway(self, skill_ids: list[str], target_role: str, current_occ: str | None = None,
                scenario: str = "moderate", snapshot_id: str | None = None, top_roles: int = 10) -> dict:
        """F5 pathway + H5 best next hour for one target role.

        Steps = the role's missing essential skills, broader ESCO concepts first, then
        by score gain for the target role. Each step gets the shortest course with
        verified hours (else one marked "hours not verified"). best_next_hour = the
        verified course with the largest gain across the user's top roles per hour.
        """
        if target_role not in self.store.occupation_ids:
            raise KeyError(f"unknown target_role_id {target_role!r}")
        sid = self.resolve_snapshot(snapshot_id)
        have = [k for k in dict.fromkeys(skill_ids) if k in self.store.skill_ids]
        base = self.rank(have, current_occ, scenario, sid).set_index("occ_id")
        top = list(base.sort_values("rank").index[:top_roles])
        missing = [k for k in self.essentials.get(target_role, []) if k not in set(have)]
        by_skill = self._courses_by_skill()
        label = self.store.skill_label
        sm = self.store["sdg_map"]
        role_row = sm[(sm.key_type == "occupation") & (sm.occ_id == target_role)]
        role_sdg = [f"SDG {g}" for g in str(role_row.iloc[0].sdg_ids).split(";") if g] if len(role_row) else []

        steps = []
        for k in missing:
            after = self.rank(have + [k], current_occ, scenario, sid).set_index("occ_id")
            gain_target = float(after.S.get(target_role, 0) - base.S.get(target_role, 0)) if target_role in base.index else 0.0
            gain_top = float(sum(max(0.0, after.S[o] - base.S[o]) for o in top if o in after.index))
            course = self._pick_course(by_skill.get(k, []))
            steps.append({"skill_id": k, "skill_name": label[k], "gain_points": round(gain_target, 2),
                          "gain_top_roles": round(gain_top, 2),
                          "rank_after": int(after["rank"][target_role]) if target_role in after.index else None,
                          "n_missing_ancestors": len(self._ancestors(k) & set(missing)), "course": course})
        steps.sort(key=lambda s: (s["n_missing_ancestors"], -s["gain_points"], s["skill_name"]))

        def rec(step: dict, i: int) -> dict:
            c = step["course"]
            verified = bool(c["hours_verified"]) and pd.notna(c["hours"])
            hours = float(c["hours"]) if verified else None
            return {"course_id": c["course_id"], "title": c["title"], "provider": c["provider"], "url": c["url"],
                    "cost": int(c["cost_myr"]) if str(c["cost_myr"]).isdigit() else None,  # None = not checked
                    "hrd_corp_claimable": None if c["hrd_claimable"] in ("", "unknown") else c["hrd_claimable"] == "true",
                    "sdg_tags": role_sdg or self._sdg_tags(c), "hours": hours if verified else "hours not verified",
                    "hours_verified": verified, "hours_method": c.get("hours_method") or None,
                    "checked_on": c.get("checked_on") or None,
                    "marginal_score_per_hour": round(step["gain_top_roles"] / hours, 3) if verified and hours else None,
                    "skill_id": step["skill_id"], "skill_name": step["skill_name"], "step": i,
                    "gain_points": step["gain_points"]}

        recs, by_course = [], {}
        for st in (s for s in steps if s["course"]):
            cid = st["course"]["course_id"]
            if cid in by_course:  # one course teaching several missing skills: list it once
                r = by_course[cid]
                r["also_covers"].append(st["skill_name"])
                r["gain_points"] = round(r["gain_points"] + st["gain_points"], 2)
                continue
            r = rec(st, len(recs) + 1)
            r["also_covers"] = []
            by_course[cid] = r
            recs.append(r)
        ranked = [r for r in recs if r["marginal_score_per_hour"] is not None]
        best = max(ranked, key=lambda r: (r["marginal_score_per_hour"], -r["step"])) if ranked else None
        verified = [r for r in recs if r["hours_verified"]]
        out = {
            "target_role_id": target_role, "target_role_title": self.store.occ_title[target_role],
            "missing_skills": [s["skill_id"] for s in steps],
            "skills_without_course": [{"skill_id": s["skill_id"], "skill_name": s["skill_name"]}
                                      for s in steps if not s["course"]],
            "pathway": recs, "best_next_hour": best,
            "totals": {"courses": len(recs), "verified_hours": round(sum(r["hours"] for r in verified), 1),
                       "unverified_courses": len(recs) - len(verified),
                       "cost_myr": sum(r["cost"] for r in recs if r["cost"] is not None),
                       "cost_unknown": sum(r["cost"] is None for r in recs)},
            "label": ESTIMATE,
            "assumption_note": ("Gain = change in match score if you add the skill (same model as the role ranking). "
                                f"Best next hour = gain summed over your top {top_roles} roles divided by verified "
                                "course hours; courses without hours checked on the course page are never ranked."),
        }
        return self._guard(out)

    # ---------- P4: Task X-ray and upgrade in place ----------
    def xray(self, occupation: str, snapshot_id: str | None = None) -> dict:
        """H1: each task of an occupation with AI usage, automation / augmentation and a label."""
        if occupation not in self.store.occupation_ids:
            raise KeyError(f"unknown occupation {occupation!r}")
        sid = self.resolve_snapshot(snapshot_id)
        cfg = self.cfg["xray"]
        ot = self.store["occ_task"]
        ot = ot[ot.occ_id == occupation].merge(self.store.task_signals(sid), left_on="task_id",
                                               right_index=True, how="left")
        text = self.store["tasks"].set_index("task_id").task
        default_auto = (self.store.country_signal(sid, "GLOBAL", "collaboration_bucket_automation_pct")
                        or 50.0) / 100
        tasks = []
        for r in ot.itertuples():
            u = None if pd.isna(r.usage_share) else float(r.usage_share)
            auto = None if pd.isna(r.automation_share) else float(r.automation_share)
            if u is None or u < cfg["min_usage_share"]:
                label = "mostly human"
                note = "no AI use observed in this sample" if u is None else "AI use below the measurable threshold"
            else:
                share = auto if auto is not None else default_auto
                label = "automating" if share >= cfg["automating_min_auto"] else "assisting"
                note = "" if auto is not None else "no published split: snapshot-wide automation share used"
            tasks.append({
                "task_id": int(r.task_id), "task": text[r.task_id], "weight_pct": round(100 * r.weight, 1),
                "usage_share_pct": None if u is None else round(100 * u, 3),
                "automation_pct": None if auto is None else round(100 * auto, 1),
                "augmentation_pct": None if pd.isna(r.augmentation_share) else round(100 * r.augmentation_share, 1),
                "label": label, "note": note,
            })
        order = {"automating": 0, "assisting": 1, "mostly human": 2}
        tasks.sort(key=lambda t: (order[t["label"]], -t["weight_pct"]))
        summary = {lab: round(sum(t["weight_pct"] for t in tasks if t["label"] == lab), 1) for lab in order}
        out = {
            "occupation_id": occupation, "occupation_title": self.store.occ_title[occupation],
            "snapshot_id": sid, "tasks": tasks, "summary_weight_pct": summary,
            "thresholds": {"min_usage_share_pct": 100 * cfg["min_usage_share"],
                           "automating_min_automation_pct": 100 * cfg["automating_min_auto"]},
            "source_badges": [self.store.badge(sid), *self.store.static_badges()[1:]],
            "label": ESTIMATE,
            "assumption_note": ("Labels apply our thresholds to observed Claude.ai usage of each O*NET task "
                                "(global, not Malaysia-specific). 'Mostly human' means no measurable AI use in "
                                "this sample, not that AI cannot do the task."),
        }
        return self._guard(out)

    def upgrade(self, occupation: str, skill_ids: list[str], scenario: str = "moderate",
                snapshot_id: str | None = None) -> dict:
        """H2: skills of the current job that support its 'assisting' tasks and the user lacks."""
        xr = self.xray(occupation, snapshot_id)
        sid = xr["snapshot_id"]
        have = set(skill_ids)
        assisting = [t for t in xr["tasks"] if t["label"] == "assisting"]
        os_ = self.store["occ_skill"]
        cand = sorted(set(os_[os_.occ_id == occupation].skill_uri) & self.store.linked_skill_ids)
        cfg = self.cfg["upgrade"]
        floor = cfg["min_similarity_lexical"] if self.sim.backend == "lexical" else cfg["min_similarity"]
        found: dict[str, dict] = {}
        if assisting and cand:
            sims = self.sim.phrases([t["task"] for t in assisting], cand)
            for i, t in enumerate(assisting):
                for j in sims[i].argsort()[::-1][:cfg["top_skills_per_task"]]:
                    if sims[i][j] < floor:
                        break
                    entry = found.setdefault(cand[j], {"tasks": [], "weight": 0.0, "sim": 0.0})
                    entry["tasks"].append({"task_id": t["task_id"], "task": t["task"]})
                    entry["weight"] += t["weight_pct"]
                    entry["sim"] = max(entry["sim"], float(sims[i][j]))
        m = self.state(sid, scenario)["m"]
        thr = self.cfg["momentum"]["radar_threshold"]
        by_skill = self._courses_by_skill()
        skills = []
        for k, e in found.items():
            if k in have:
                continue
            c = self._pick_course(by_skill.get(k, []))
            mk = float(m.get(k, 0.0))
            course = None
            if c is not None:
                ok = bool(c["hours_verified"]) and pd.notna(c["hours"])
                course = {"course_id": c["course_id"], "title": c["title"], "url": c["url"],
                          "hours": float(c["hours"]) if ok else "hours not verified", "hours_verified": ok}
            skills.append({"skill_id": k, "skill_name": self.store.skill_label[k],
                           "supports_tasks": e["tasks"], "task_weight_pct": round(e["weight"], 1),
                           "similarity": round(e["sim"], 3), "momentum": round(mk, 3),
                           "momentum_status": model.radar_status(mk, thr), "course": course})
        skills.sort(key=lambda x: (-x["task_weight_pct"], -x["momentum"], x["skill_name"]))
        out = {
            "occupation_id": occupation, "occupation_title": xr["occupation_title"], "snapshot_id": sid,
            "assisting_tasks": len(assisting), "skills": skills[:cfg["max_results"]],
            "source_badges": xr["source_badges"], "label": ESTIMATE,
            "assumption_note": ("Skills of your current job (ESCO) most similar to the tasks where AI assists "
                                "rather than automates: adding them is the 'AI-upgraded' version of your role. "
                                "Task-skill links are text similarity, not an official mapping."),
        }
        return self._guard(out)

    def team(self, members: list[dict] | None = None, scenario: str = "moderate",
             snapshot_id: str | None = None, top: int = 3) -> dict:
        """HR heatmap: per member, the current job's X-ray split and their top roles.

        members: [{"id", "name", "current_occ_id", "skill_ids" | "skills" or "current_skills" (free text)}];
        default = the synthetic HR cohort of the active personas file.
        """
        sid = self.resolve_snapshot(snapshot_id)
        if members is None:
            members = self.personas().get("hr_team_cohort", [])
        rows = []
        for mbr in members:
            occ = mbr.get("current_occ_id")
            if occ not in self.store.occupation_ids:
                occ = None
            ids = [k for k in mbr.get("skill_ids") or [] if k in self.store.skill_ids]
            text_skills = mbr.get("skills") or mbr.get("current_skills") or []
            if not ids and text_skills:  # free-text skills (e.g. "CRM Software") -> ESCO matches
                ids = [f["skill_id"] for f in self.parse("\n".join(text_skills))]
            split = self.xray(occ, sid)["summary_weight_pct"] if occ else None
            ranked = self.rank(ids, occ, scenario, sid)
            rows.append({
                "id": str(mbr.get("id", "")), "name": mbr.get("name", ""), "current_occ_id": occ,
                "current_title": self.store.occ_title.get(occ) if occ else None,
                "skills_matched": len(ids), "task_split_pct": split,
                "top_roles": [{"role_id": r.occ_id, "role_title": self.store.occ_title[r.occ_id],
                               "score": round(float(r.S), 1)} for r in ranked.head(top).itertuples()],
            })
        return self._guard({"snapshot_id": sid, "scenario": scenario, "members": rows,
                            "source_badges": [self.store.badge(sid), *self.store.static_badges()],
                            "label": ESTIMATE,
                            "assumption_note": "Synthetic cohort. Task split = Task X-ray of each member's "
                                               "current job; roles = the same match model as for individuals."})


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return Engine()
