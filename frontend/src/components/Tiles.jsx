import { Estimate, Source } from "./Badge";

export function MalaysiaTile({ ctx }) {
  if (!ctx) return <div className="card tile"><p className="skeleton">Loading…</p></div>;
  const idx = ctx.malaysia_usage_index;
  return (
    <div className="card tile" title={ctx.label}>
      <p className="label" style={{ margin: 0 }}>Malaysia</p>
      <div>
        <div className="n">{idx != null ? idx.toFixed(2) : "–"}</div>
        <div className="sub">
          {idx != null ? "AI usage per working-age person, world = 1.00" : "Usage index not published in this release"}
        </div>
        {ctx.malaysia_automation_pct != null && (
          <div className="sub">
            {Math.round(ctx.malaysia_automation_pct)}% of AI use is automation, not assistance
            {ctx.global_automation_pct != null && ` (world ${Math.round(ctx.global_automation_pct)}%)`}
          </div>
        )}
      </div>
      <Source badge={ctx.badge} />
    </div>
  );
}

export function SafestTile({ role, note }) {
  return (
    <div className="card tile dim">
      <p className="label" style={{ margin: 0 }}>Safest pick</p>
      {role ? (
        <div>
          <div className="who">{role.role_title}</div>
          <div className="sub">
            Never below #{role.robustness.worst_rank} in {role.robustness.runs.toLocaleString()} futures
          </div>
        </div>
      ) : <div className="sub">Appears after your skills are read</div>}
      <Estimate note={note} />
    </div>
  );
}
