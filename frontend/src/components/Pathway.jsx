import { useState } from "react";
import * as api from "../api";
import { Estimate, Source } from "./Badge";

const BEST_LABEL = "Highest estimated gain per verified study hour in our catalogue";
// Off until the API flags its generic fallback list: with no flag, the rule below shows a "best"
// course for roles whose list is not linked to their missing skills. Set to true to switch it back on.
const SHOW_BEST_NEXT_HOUR = false;
const MISSING_SHOWN = 5;
// The API has no fallback flag: when no course covers a missing skill it returns a generic
// list instead, and the frontend cannot tell the two cases apart. So the wording stays neutral.
const CATALOGUE_NOTE = "The catalogue does not always link each course to your missing skills, "
  + "so treat this as a starting point, not a complete plan.";

const verified = (c) => c.hours_verified === true && typeof c.hours === "number";
const costText = (cost) =>
  cost == null ? "cost unknown" : cost === 0 ? "free (unverified)" : `RM ${cost.toLocaleString()} (unverified)`;
const hrdText = (v) =>
  v === true ? "HRD Corp claimable" : v === false ? "not HRD Corp claimable" : "HRD Corp: unknown";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

/** Names only when the pathway lists the same missing skills, in the same order, as the match result. */
function missingNamesFor(pathIds, roleIds, roleNames) {
  if (!roleIds || !roleNames || roleNames.length !== roleIds.length) return null;
  if (pathIds.length !== roleIds.length || pathIds.some((id, i) => id !== roleIds[i])) return null;
  return roleNames;
}

/** Learning pathway for one role, loaded on demand. Never breaks on 501 or errors. */
export default function Pathway({ skillIds, roleId, missingIds, missingNames, note }) {
  const [state, setState] = useState({ status: "idle" });
  const [allMissing, setAllMissing] = useState(false);

  const load = async () => {
    setState({ status: "loading" });
    try {
      setState({ status: "ready", data: await api.getPathway(skillIds, roleId) });
    } catch (e) {
      setState({ status: e.status === 501 ? "soon" : "error", error: e.message });
    }
  };

  if (state.status === "idle") {
    return (
      <button className="pill small ghost" onClick={load} style={{ justifySelf: "start" }}>
        Learning pathway
      </button>
    );
  }
  if (state.status === "loading") {
    return <p className="faint" style={{ margin: 0 }}><span className="spin" /> Loading learning pathway…</p>;
  }
  if (state.status === "soon") {
    return <p className="note" style={{ margin: 0 }}>Learning pathway is coming soon.</p>;
  }
  if (state.status === "error") {
    return (
      <p className="warn" role="alert" style={{ margin: 0 }}>
        Couldn't load the learning pathway ({state.error}).{" "}
        <button className="linkish" onClick={load}>Try again</button>
      </p>
    );
  }

  const data = state.data || {};
  const courses = data.pathway || [];
  const pathMissing = data.missing_skills || [];
  const names = missingNamesFor(pathMissing, missingIds, missingNames);
  const best = data.best_next_hour;
  const showBest = SHOW_BEST_NEXT_HOUR && best && verified(best)
    && typeof best.marginal_score_per_hour === "number" && best.marginal_score_per_hour > 0;
  const hoursTotal = courses.filter(verified).reduce((n, c) => n + c.hours, 0);
  const nVerified = courses.filter(verified).length;
  const badges = [...new Map(courses.flatMap((c) => c.source_badges || [])
    .map((b) => [`${b.source}|${b.date}`, b])).values()];
  const estNote = note || data.assumption_note;
  // the API copies the target role's SDG tags onto every course, so they are shown once, as the role's
  const roleSdg = [...new Set(courses.flatMap((c) => c.sdg_tags || []))];
  const missingShown = names && !allMissing ? names.slice(0, MISSING_SHOWN) : names;

  return (
    <div className="pathway-wrap">
      <div className="pathway-head">
        <p className="faint" style={{ fontSize: 12, margin: 0 }}>Learning pathway</p>
        <Estimate note={estNote} />
      </div>

      {roleSdg.length > 0 && (
        <p className="pathway-missing" title="These are the target role's SDG links, not the course's">
          This role's SDG links: {roleSdg.join(", ")}
        </p>
      )}

      <p className="pathway-missing">
        {pathMissing.length === 0 ? "No missing skills listed for this role."
          : names ? (
            <>
              Skills to add ({names.length}): {missingShown.join(", ")}
              {names.length > MISSING_SHOWN && (
                <>{" "}<button className="linkish" onClick={() => setAllMissing(!allMissing)}>
                  {allMissing ? "fewer" : `+${names.length - MISSING_SHOWN} more`}
                </button></>
              )}
            </>
          ) : `${plural(pathMissing.length, "missing skill")} for this role.`}
      </p>

      {courses.length === 0 ? (
        <p className="faint" style={{ margin: 0 }}>No courses returned by our catalogue for this role.</p>
      ) : (
        <>
          {showBest && (
            <div className="best-hour">
              <p className="faint" style={{ fontSize: 12, margin: 0 }}>
                {BEST_LABEL} <Estimate note={estNote} />
              </p>
              <p style={{ margin: "4px 0 0" }}>
                {best.url ? <a href={best.url} target="_blank" rel="noreferrer">{best.title}</a> : best.title}
                <span className="faint"> · {best.provider} · {best.hours} h · {best.marginal_score_per_hour} per hour</span>
              </p>
              <p className="faint" style={{ fontSize: 12, margin: "4px 0 0" }}>
                Based on {best.hours} verified hours. This assumes the course teaches one of this role's skills;
                the catalogue does not always confirm that.
              </p>
            </div>
          )}

          <p className="faint" style={{ fontSize: 12.5, margin: 0 }}>
            Courses returned by our catalogue for this role ({courses.length}). {CATALOGUE_NOTE}
          </p>
          <ol className="pathway">
            {courses.map((c, i) => (
              <li key={c.course_id || c.title}>
                <span className="pathway-n">{i + 1}</span>
                <div>
                  {c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.title}</a> : c.title}
                  <div className="faint pathway-meta">
                    {c.provider && <span>{c.provider}</span>}
                    <span>{verified(c) ? `${c.hours} h` : "hours not verified"}</span>
                    <span>{costText(c.cost)}</span>
                    <span>{hrdText(c.hrd_corp_claimable)}</span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
          <p className="faint" style={{ fontSize: 12, margin: 0 }}>
            {hoursTotal} verified hours across {plural(nVerified, "course")}
            {courses.length - nVerified > 0 && ` · ${plural(courses.length - nVerified, "course")} without verified hours`}
          </p>
        </>
      )}

      <div className="sources">
        {badges.map((b) => <Source key={`${b.source}|${b.date}`} badge={b} />)}
        <Estimate note={estNote} />
      </div>
    </div>
  );
}
