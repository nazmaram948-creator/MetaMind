import { useState } from "react";
import { Movement } from "../RoleCard";
import { Estimate, Source } from "./Badge";

export default function DiffCard({ diff, labels, onUndo, busy }) {
  const [why, setWhy] = useState(null);
  const moved = diff.changes.filter((c) => c.movement !== 0);
  return (
    <section className="card diff" aria-live="polite">
      <div className="roles-head" style={{ marginBottom: 0 }}>
        <p className="label" style={{ margin: 0, color: "var(--text)" }}>
          {labels.from} → {labels.to}: {moved.length ? `${moved.length} of your top roles moved` : "your top roles held their places"}
        </p>
        <span style={{ display: "inline-flex", gap: 10, alignItems: "center" }}>
          <Source badge={diff.changes[0]?.source} />
          <Estimate note={diff.assumption_note} />
          <button className="pill small ghost" onClick={onUndo} disabled={busy}>Back to {labels.from}</button>
        </span>
      </div>
      <ul className={diff.changes.length > 8 ? "scroll" : undefined}>
        {diff.changes.map((c) => (
          <li key={c.role_id}>
            <span>
              <button className="linkish" style={{ color: "var(--text)", textDecoration: "none" }}
                onClick={() => setWhy(why === c.role_id ? null : c.role_id)}>
                {c.role_title}
              </button>{" "}
              <span className="faint" style={{ fontSize: 12.5 }}>#{c.old_rank} → #{c.new_rank} · {c.driving_metric}</span>
              {why === c.role_id && <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{c.explanation}</div>}
            </span>
            <Movement value={c.movement} />
          </li>
        ))}
      </ul>
    </section>
  );
}
