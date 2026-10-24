import { useEffect, useMemo, useRef, useState } from "react";
import * as api from "../api";
import RoleCard from "../RoleCard";
import { Estimate } from "./Badge";

const SORTS = {
  match: ["Best match", (a, b) => a.rank - b.rank],
  robust: ["Most robust", (a, b) => b.robustness.top5_frequency - a.robustness.top5_frequency || a.rank - b.rank],
  skills: ["Most skills held", (a, b) => b.score_breakdown.skills_covered_score - a.score_breakdown.skills_covered_score],
  outlook: ["Best outlook", (a, b) => b.score_breakdown.role_trend_score - a.score_breakdown.role_trend_score],
};

const STEPS = [0, 0.25, 0.5, 0.75, 1];
const DEBOUNCE_MS = 250; // every /api/match runs the futures simulation, so wait for the slider to settle
const SDG_HINT = "Blends your skill fit with how many SDGs each role is linked to. 0 = fit only. "
  + "Estimate based on a first-pass mapping flagged for review.";

const ranksOf = (roles) => Object.fromEntries(roles.map((r) => [r.role_id, r.rank]));

export default function Roles({ result, movements, current, sdg, skillIds, scenario, currentId }) {
  const [sort, setSort] = useState("match");
  const [all, setAll] = useState(false);

  const [pref, setPref] = useState(0);
  const [view, setView] = useState(null); // { roles, ranks, pref } from the last slider response
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const seq = useRef(0); // only the newest request may update the list
  const movedFor = useRef(null); // the result the slider was last moved on
  const base = useRef({ result: null, key: null, ranks: null }); // ranks at slider 0, per result + inputs

  useEffect(() => {
    const id = ++seq.current;
    // untouched slider at 0: show the ranking App already fetched, no extra call
    if (pref === 0 && movedFor.current !== result) {
      setView(null);
      setLoading(false);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    const key = JSON.stringify([skillIds, currentId, scenario]);
    const timer = setTimeout(async () => {
      try {
        const cached = base.current.result === result && base.current.key === key ? base.current.ranks : null;
        const [out, zero] = await Promise.all([
          api.matchRoles(skillIds, currentId, scenario, pref),
          cached || pref === 0 ? null : api.matchRoles(skillIds, currentId, scenario, 0),
        ]);
        if (id !== seq.current) return;
        if (!cached) base.current = { result, key, ranks: ranksOf((zero || out).roles) };
        setView({ roles: out.roles, ranks: base.current.ranks, pref });
      } catch (e) {
        if (id === seq.current) setError(e.message);
      } finally {
        if (id === seq.current) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // skills, job and scenario are read when a request fires; a new result is what triggers a refetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, pref, retry]);

  const onSlide = (e) => {
    movedFor.current = result;
    setPref(STEPS[Number(e.target.value)]);
  };

  const list = view ? view.roles : result.roles;
  const roles = useMemo(() => [...list].sort(SORTS[sort][1]), [list, sort]);
  const shown = all ? roles : roles.slice(0, 8);
  const blended = view && view.pref > 0;

  return (
    <section className="card" id="roles">
      <div className="roles-head">
        <p className="label" style={{ margin: 0 }}>
          Roles for you{current ? `, moving from ${current}` : ""}
        </p>
        <span style={{ display: "inline-flex", gap: 10, alignItems: "center" }}>
          <Estimate note={result.assumption_note} />
          <select className="pill small" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort roles">
            {Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </span>
      </div>

      <div className="sdg-slider">
        <div className="sdg-slider-row">
          <label htmlFor="sdg-pref" className="faint">SDG weight</label>
          <div className="sdg-slider-track">
            <input id="sdg-pref" type="range" min={0} max={STEPS.length - 1} step={1}
              value={STEPS.indexOf(pref)} onChange={onSlide}
              aria-valuetext={pref === 0 ? "0, fit only" : String(pref)} />
            <div className="sdg-ticks" aria-hidden="true">
              {STEPS.map((s) => <span key={s} className={s === pref ? "on" : ""}>{s}</span>)}
            </div>
          </div>
          <Estimate note="SDG weighting uses a first-pass SDG mapping flagged for review" />
          {loading && <span className="faint sdg-status"><span className="spin" /> Re-ranking…</span>}
        </div>
        <p className="faint sdg-hint">{SDG_HINT}</p>
        {error && (
          <p className="error" role="alert" style={{ margin: "6px 0 0" }}>
            Couldn't re-rank with the SDG weight ({error}). Showing the last ranking.{" "}
            <button className="linkish" onClick={() => setRetry((n) => n + 1)}>Try again</button>
          </p>
        )}
      </div>

      <p className="roles-hint">Click a role to see its score breakdown, SDG links and a learning pathway.</p>

      <div className={loading ? "roles-busy" : ""} aria-busy={loading}>
        <div className="cols" aria-hidden="true">
          <span /><span>Role</span><span>Match</span><span>Stays in top 5</span><span>Range, P10–P90</span><span />
        </div>
        {shown.map((r) => (
          <RoleCard key={r.role_id} role={r} movement={movements?.[r.role_id]} note={result.assumption_note}
            sdg={sdg} skillIds={skillIds} sdgPref={view?.pref ?? 0}
            sdgDelta={blended && view.ranks[r.role_id] != null ? view.ranks[r.role_id] - r.rank : null} />
        ))}
        {roles.length > 8 && (
          <button className="pill small ghost more" onClick={() => setAll(!all)}>
            {all ? "Show top 8" : `Show all ${roles.length}`}
          </button>
        )}
      </div>
    </section>
  );
}
