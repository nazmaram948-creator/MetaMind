import { useMemo, useState } from "react";
import RoleCard from "../RoleCard";
import { Estimate } from "./Badge";

const SORTS = {
  match: ["Best match", (a, b) => a.rank - b.rank],
  robust: ["Most robust", (a, b) => b.robustness.top5_frequency - a.robustness.top5_frequency || a.rank - b.rank],
  skills: ["Most skills held", (a, b) => b.score_breakdown.skills_covered_score - a.score_breakdown.skills_covered_score],
  outlook: ["Best outlook", (a, b) => b.score_breakdown.role_trend_score - a.score_breakdown.role_trend_score],
};

export default function Roles({ result, movements, current }) {
  const [sort, setSort] = useState("match");
  const [all, setAll] = useState(false);
  const roles = useMemo(() => [...result.roles].sort(SORTS[sort][1]), [result, sort]);
  const shown = all ? roles : roles.slice(0, 8);

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
      <div className="cols" aria-hidden="true">
        <span /><span>Role</span><span>Match</span><span>Stays in top 5</span><span>Range, P10–P90</span><span />
      </div>
      {shown.map((r) => (
        <RoleCard key={r.role_id} role={r} movement={movements?.[r.role_id]} note={result.assumption_note} />
      ))}
      {roles.length > 8 && (
        <button className="pill small ghost more" onClick={() => setAll(!all)}>
          {all ? "Show top 8" : `Show all ${roles.length}`}
        </button>
      )}
    </section>
  );
}
