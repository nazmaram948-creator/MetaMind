import { useMemo, useState } from "react";
import { Estimate, Source } from "./Badge";
import { SDG_NAMES, SDG_NOTE, firstClause } from "./sdgData";

const TOP = 8; // same cut as the roles list

export function SdgTags({ goals, compact }) {
  return goals.map((g) => (
    <span key={g} className="tag sdg" title={SDG_NAMES[g] ? `SDG ${g}: ${SDG_NAMES[g]}` : `SDG ${g}`}>
      SDG {g}{!compact && SDG_NAMES[g] ? ` · ${SDG_NAMES[g]}` : ""}
    </span>
  ));
}

export function SdgReason({ text }) {
  const [all, setAll] = useState(false);
  const first = firstClause(text);
  return (
    <p className="sdg-why">
      {all ? text : first}
      {first.length < text.length && (
        <>{" "}<button className="linkish" onClick={() => setAll(!all)}>{all ? "less" : "more"}</button></>
      )}
    </p>
  );
}

/** Filterable list of every target occupation with the SDG links /api/sdg returns for it. */
export default function Sdg({ sdg, occupations, result, onRetry }) {
  const [goal, setGoal] = useState(null);
  const [query, setQuery] = useState("");
  const [topOnly, setTopOnly] = useState(false);

  const rows = useMemo(() => {
    const titles = occupations.length ? occupations.map((o) => o.title) : sdg.rows.map((r) => r.occupation);
    const ranked = Object.fromEntries((result?.roles || []).map((r) => [r.role_title.toLowerCase(), r]));
    const list = titles.map((title) => ({ title, rec: sdg.index[title.toLowerCase()], role: ranked[title.toLowerCase()] }));
    // with results: your ranking first (your current job is not ranked, so it goes last)
    return list.sort((a, b) => (a.role?.rank ?? Infinity) - (b.role?.rank ?? Infinity) || a.title.localeCompare(b.title));
  }, [occupations, sdg, result]);

  const counts = useMemo(() => {
    const c = {};
    rows.forEach((r) => r.rec?.goals.forEach((g) => { c[g] = (c[g] || 0) + 1; }));
    return Object.entries(c).map(([g, n]) => [Number(g), n]).sort((a, b) => a[0] - b[0]);
  }, [rows]);

  const q = query.trim().toLowerCase();
  const shown = rows.filter((r) =>
    (!goal || r.rec?.goals.includes(goal)) &&
    (!q || r.title.toLowerCase().includes(q)) &&
    (!topOnly || (r.role && r.role.rank <= TOP)));

  const head = (
    <div className="roles-head">
      <p className="label" style={{ margin: 0 }}>SDG links by role</p>
      {result && (
        <span className="sources" title="Rank and match score are model output">
          <Estimate note={result.assumption_note} />
          {result.roles[0]?.source_badges.map((b) => <Source key={b.source} badge={b} />)}
        </span>
      )}
    </div>
  );

  if (sdg.status === "loading") {
    return <section className="card" id="sdg">{head}<p className="skeleton">Loading SDG links…</p></section>;
  }
  if (sdg.status === "error") {
    return (
      <section className="card" id="sdg">
        {head}
        <div className="warn" role="alert" style={{ marginBottom: 0 }}>
          Couldn't load SDG links. The API may be down or returned an error ({sdg.error}).{" "}
          <button className="linkish" onClick={onRetry}>Try again</button>
        </div>
      </section>
    );
  }
  if (sdg.rows.length === 0) {
    return <section className="card" id="sdg">{head}<p className="skeleton">No SDG links available yet.</p></section>;
  }

  return (
    <section className="card" id="sdg">
      {head}
      <div className="sdg-filters">
        <div className="chips" style={{ maxHeight: "none" }} role="group" aria-label="Filter by goal">
          <button type="button" className={`chip${goal ? "" : " on"}`} onClick={() => setGoal(null)}>All</button>
          {counts.map(([g, n]) => (
            <button key={g} type="button" className={`chip${goal === g ? " on" : ""}`} aria-pressed={goal === g}
              title={SDG_NAMES[g] || undefined} onClick={() => setGoal(goal === g ? null : g)}>
              SDG {g}{SDG_NAMES[g] ? ` · ${SDG_NAMES[g]}` : ""} <span className="conf">{n}</span>
            </button>
          ))}
        </div>
        <div className="controls">
          <input className="pill small sdg-search" type="search" value={query} placeholder="Search roles"
            aria-label="Search roles" onChange={(e) => setQuery(e.target.value)} />
          {result && (
            <label className="sdg-toggle">
              <input type="checkbox" checked={topOnly} onChange={(e) => setTopOnly(e.target.checked)} />
              Only my top {TOP} roles
            </label>
          )}
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="skeleton">
          {goal ? `No roles linked to SDG ${goal}` : "No roles match"}{q || topOnly ? " with these filters" : ""}.{" "}
          <button className="linkish" onClick={() => { setGoal(null); setQuery(""); setTopOnly(false); }}>Reset filters</button>
        </p>
      ) : (
        <ul className="sdg-list">
          {shown.map(({ title, rec, role }) => (
            <li key={title} className="sdg-row">
              <div className="sdg-top">
                <span className="rtitle">{title}</span>
                {role && (
                  <span className="sdg-you">
                    <b>#{role.rank}</b> · {role.total_match_score.toFixed(0)} match <Estimate note={result.assumption_note} />
                  </span>
                )}
              </div>
              {rec ? (
                <>
                  <div className="sdg-tags"><SdgTags goals={rec.goals} /></div>
                  <SdgReason text={rec.reasoning} />
                </>
              ) : (
                <p className="faint sdg-why">No SDG link in the data</p>
              )}
            </li>
          ))}
        </ul>
      )}

      <p className="faint" style={{ fontSize: 12, margin: "12px 0 0" }}>
        {SDG_NOTE}. Goal names are the official UN titles. {shown.length} of {rows.length} roles shown.
      </p>
    </section>
  );
}
