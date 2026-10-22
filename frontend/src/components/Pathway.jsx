import { useState } from "react";
import * as api from "../api";

/** Placeholder until the P2 pathway: asks the API on demand and never breaks on 501 or errors. */
export default function Pathway({ skillIds, roleId }) {
  const [state, setState] = useState({ status: "idle" });

  const load = async () => {
    setState({ status: "loading" });
    try {
      setState({ status: "ready", data: await api.getPathway(skillIds, roleId) });
    } catch (e) {
      setState({ status: e.status === 501 ? "soon" : "error", error: e.message });
    }
  };

  if (state.status === "idle" || state.status === "loading") {
    return (
      <button className="pill small ghost" onClick={load} disabled={state.status === "loading"} style={{ justifySelf: "start" }}>
        {state.status === "loading" ? <span className="spin" /> : null} Learning pathway
      </button>
    );
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

  const courses = state.data?.pathway || [];
  if (!courses.length) return <p className="faint" style={{ margin: 0 }}>No courses found for this role yet.</p>;
  return (
    <ul className="pathway">
      {courses.map((c) => (
        <li key={c.course_id || c.title}>
          {c.url ? <a href={c.url} target="_blank" rel="noreferrer">{c.title}</a> : c.title}
          <span className="faint">
            {c.provider ? ` · ${c.provider}` : ""} ·{" "}
            {c.hours_verified === true ? `${c.hours} h${c.cost != null ? ` · cost ${c.cost}` : ""}` : "hours not verified"}
          </span>
        </li>
      ))}
    </ul>
  );
}
