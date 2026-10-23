const fmt = (d) => {
  if (!d) return "";
  const t = new Date(d);
  return Number.isNaN(t.getTime()) ? d : t.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
};

const short = (s = "") =>
  s.replace("Anthropic Economic Index (Claude.ai, global), ", "")
    .replace("SkillShift estimate from ", "")
    .replace("Anthropic Economic Index (Claude.ai, global)", "AEI")
    .replace(" (ESCO Web Service API)", "")
    .replace(", U.S. Department of Labor/ETA", "");

/** Source + date for a number. Full source in the tooltip, link when we have one. */
export function Source({ badge }) {
  if (!badge) return null;
  const text = `${short(badge.source)} · ${badge.date_kind === "retrieved" ? "retrieved " : ""}${fmt(badge.date)}`;
  const title = [badge.source, badge.period && `data ${badge.period}`, badge.date && `${badge.date_kind || "published"} ${badge.date}`]
    .filter(Boolean).join(" — ");
  return badge.url ? (
    <a className="badge" href={badge.url} target="_blank" rel="noreferrer" title={title}>{text}</a>
  ) : (
    <span className="badge" title={title}>{text}</span>
  );
}

export function Estimate({ note }) {
  return <span className="est" title={note || "Model output, not a fact"}>Estimate</span>;
}
