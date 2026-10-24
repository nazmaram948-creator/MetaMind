import { useState } from "react";
import Icon from "./components/Icon";
import { Estimate, Source } from "./components/Badge";
import { SdgReason, SdgTags } from "./components/Sdg";
import { SDG_NOTE, goalsOf } from "./components/sdgData";
import Pathway from "./components/Pathway";

const PART = [
  ["coverage", "Skills you have", "var(--lime)"],
  ["outlook", "Role outlook", "var(--orange)"],
  ["transferability", "Transferable", "var(--sky)"],
];

export function Movement({ value, title = "Rank change with the newer data" }) {
  if (value == null || value === 0) return null;
  const up = value > 0;
  return (
    <span className={`mv ${up ? "up" : "down"}`} title={title}>
      <Icon name={up ? "arrowUp" : "arrowDown"} size={13} stroke={2.2} />{Math.abs(value)}
    </span>
  );
}

function SdgBlock({ sdg, rec }) {
  return (
    <div className="sdg-block">
      <p className="faint" style={{ fontSize: 12, margin: 0 }}>SDG links</p>
      {sdg.status === "loading" ? <p className="faint sdg-why">Loading SDG links…</p>
        : sdg.status === "error" ? <p className="faint sdg-why">SDG links are unavailable right now.</p>
        : rec ? (
          <>
            <div className="sdg-tags"><SdgTags goals={rec.goals} /></div>
            <SdgReason text={rec.reasoning} />
          </>
        ) : <p className="faint sdg-why">No SDG link in the data</p>}
      <p className="faint" style={{ fontSize: 11, margin: 0 }}>{SDG_NOTE}</p>
    </div>
  );
}

/** Goals from the /api/match role itself; null when the response has no SDG fields at all. */
function matchGoals(role) {
  if (!Array.isArray(role.sdg_ids) && !Array.isArray(role.sdg_tags)) return null;
  const ids = (role.sdg_ids || []).map(Number).filter((g) => g >= 1 && g <= 17);
  return ids.length ? ids : goalsOf((role.sdg_tags || []).join(";"));
}

export default function RoleCard({ role, movement, note, sdg, skillIds, sdgPref = 0, sdgDelta }) {
  const [open, setOpen] = useState(false);
  const [allGaps, setAllGaps] = useState(false);
  const r = role.robustness;
  const pts = role.score_points || {};
  const gaps = role.missing_skill_names || role.missing_skills;
  const shown = allGaps ? gaps : gaps.slice(0, 8);
  const exposure = role.ai_exposure;
  const sdgRec = sdg?.index[role.role_title.toLowerCase()];
  const goals = matchGoals(role);
  // above 0 the API blends the total, so the parts no longer add up to it
  const blended = sdgPref > 0;

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
            {sdgDelta ? (
              <span className="sdg-mv"><span className="faint">SDG</span>
                <Movement value={sdgDelta} title="Rank change vs SDG slider 0" /></span>
            ) : null}
            {goals ? (
              goals.length ? <SdgTags goals={goals} compact />
                : <span className="faint" style={{ fontSize: 12 }}>No SDG link in the data</span>
            ) : sdgRec && <SdgTags goals={sdgRec.goals} compact />}
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
        {/* visual hint only: aria-expanded on the button already tells assistive tech the state */}
        <span className="c-more" aria-hidden="true">
          <span className="more-label">{open ? "Hide" : "Details"}</span>
          <Icon name="chevron" size={22} stroke={2} className="chev" />
        </span>
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
              <span className="faint">
                {blended ? `before blending · total ${role.total_match_score.toFixed(1)}` : `of ${role.total_match_score.toFixed(1)}`}
              </span>
            </div>
            {pts.sdg != null && (
              <p className="faint sdg-part">
                SDG link {pts.sdg.toFixed(1)} points
                {blended && " · parts shown before blending, so they do not add up to the total"}
              </p>
            )}
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

          {sdg && <SdgBlock sdg={sdg} rec={sdgRec} />}

          <Pathway skillIds={skillIds} roleId={role.role_id} missingIds={role.missing_skills}
            missingNames={role.missing_skill_names} note={note} />

          <div className="sources">
            {role.source_badges.map((b) => <Source key={b.source} badge={b} />)}
            <Estimate note={note} />
          </div>
        </div>
      )}
    </div>
  );
}
