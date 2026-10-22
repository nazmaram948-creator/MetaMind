import { useState } from "react";
import Icon from "./components/Icon";
import { Estimate, Source } from "./components/Badge";

const PART = [
  ["coverage", "Skills you have", "var(--lime)"],
  ["outlook", "Role outlook", "var(--orange)"],
  ["transferability", "Transferable", "var(--sky)"],
];

export function Movement({ value }) {
  if (value == null || value === 0) return null;
  const up = value > 0;
  return (
    <span className={`mv ${up ? "up" : "down"}`} title="Rank change with the newer data">
      <Icon name={up ? "arrowUp" : "arrowDown"} size={13} stroke={2.2} />{Math.abs(value)}
    </span>
  );
}

export default function RoleCard({ role, movement, note }) {
  const [open, setOpen] = useState(false);
  const [allGaps, setAllGaps] = useState(false);
  const r = role.robustness;
  const pts = role.score_points || {};
  const gaps = role.missing_skill_names || role.missing_skills;
  const shown = allGaps ? gaps : gaps.slice(0, 8);
  const exposure = role.ai_exposure;

  return (
    <div className={`role${open ? " open" : ""}`}>
      <button className="role-row" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="rank">{role.rank}</span>
        <span className="c-title">
          <span className="rtitle">{role.role_title}</span>
          <span className="rmeta">
            {r.safest_pick && <span className="tag lime">Safest pick</span>}
            <span className="faint" style={{ fontSize: 12 }}>
              you have {role.matched_skills.length} of {role.essential_skills_total} skills this role needs
            </span>
            <Movement value={movement} />
          </span>
        </span>
        <span className="c-score score">{role.total_match_score.toFixed(0)}</span>
        <span className="c-yes yes">
          <i className="dot" style={{ background: r.top5_frequency >= 0.5 ? "var(--lime)" : "var(--coral)" }} />
          {Math.round(r.top5_frequency * 100)}% of futures
        </span>
        <span className="c-range">
          <div className="range" title={`P10 ${r.p10} · median ${r.median_score} · P90 ${r.p90}`}>
            <i style={{ left: `${r.p10}%`, width: `${Math.max(r.p90 - r.p10, 1)}%` }} />
            <b style={{ left: `calc(${r.median_score}% - 1px)` }} />
          </div>
          <div className="range-n">{r.p90 - r.p10 < 1 ? `steady at ${r.median_score.toFixed(0)}` : `${r.p10.toFixed(0)}–${r.p90.toFixed(0)}`}</div>
        </span>
        <Icon name="chevron" className="chev" />
      </button>

      {/* outside the button: badges can be links. The open body repeats them in full. */}
      {!open && (
        <div className="role-foot">
          <Estimate note={note} />
          {role.source_badges.map((b) => <Source key={b.source} badge={b} />)}
        </div>
      )}

      {open && (
        <div className="role-body">
          <div>
            <div className="parts" aria-label="Score parts">
              {PART.map(([k, , c]) => <i key={k} style={{ width: `${pts[k] || 0}%`, background: c }} />)}
            </div>
            <div className="parts-legend">
              {PART.map(([k, label, c]) => (
                <span key={k}><i className="dot" style={{ background: c }} />{label} {(pts[k] || 0).toFixed(1)}</span>
              ))}
              <span className="faint">of {role.total_match_score.toFixed(1)}</span>
            </div>
          </div>

          <div className="facts">
            <span><b>{role.matched_skills.length} of {role.essential_skills_total}</b>skills this role needs</span>
            <span><b>{role.score_breakdown.role_trend_score.toFixed(0)}/100</b>outlook</span>
            {exposure?.automation_share_pct != null && (
              <span title={`Share of observed AI use on this role's tasks that is automation (vs augmentation). Observed tasks cover ${exposure.observed_task_weight_pct}% of the role's task weight.`}>
                <b>{exposure.automation_share_pct.toFixed(0)}%</b>of AI use automates its tasks
              </span>
            )}
            <span><b>{r.median_score.toFixed(0)}</b>median of {r.runs.toLocaleString()} futures</span>
          </div>

          {role.matched_skills.length > 0 && (
            <div className="chips" style={{ maxHeight: "none" }}>
              {(role.matched_skill_names || role.matched_skills).map((s) => (
                <span key={s} className="chip have"><Icon name="check" size={12} stroke={2.2} />{s}</span>
              ))}
            </div>
          )}
          {gaps.length > 0 && (
            <div>
              <div className="chips" style={{ maxHeight: "none" }}>
                {shown.map((s) => <span key={s} className="chip gap">{s}</span>)}
                {gaps.length > 8 && (
                  <button className="chip" onClick={() => setAllGaps(!allGaps)}>
                    {allGaps ? "fewer" : `+${gaps.length - 8} more`}
                  </button>
                )}
              </div>
              <p className="faint" style={{ fontSize: 12, margin: "8px 0 0" }}>Skills to add for this role</p>
            </div>
          )}

          <div className="sources">
            {role.source_badges.map((b) => <Source key={b.source} badge={b} />)}
            <Estimate note={note} />
          </div>
        </div>
      )}
    </div>
  );
}
