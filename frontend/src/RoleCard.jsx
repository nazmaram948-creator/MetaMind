const prettify = (id) =>
  id.replace(/^skill-/, "").replace(/-/g, " ");

function Bar({ label, value }) {
  return (
    <div style={{ marginBottom: 6 }}>
      <div style={{ fontSize: 13 }}>{label}: {value}</div>
      <div style={{ background: "rgba(255,255,255,0.15)", height: 8, borderRadius: 4 }}>
        <div style={{ width: `${value}%`, background: "#4f9cf9", height: 8, borderRadius: 4 }} />
      </div>
    </div>
  );
}

export default function RoleCard({ role, rank }) {
  const b = role.score_breakdown;
  return (
    <div style={{
      border: "1px solid rgba(255,255,255,0.2)",
      background: "rgba(255,255,255,0.05)",
      borderRadius: 8, padding: 16, margin: "12px 0", textAlign: "left",
    }}>
      <h3 style={{ margin: 0 }}>
        #{rank} {role.role_title}: {role.total_match_score}% match
      </h3>

      <div style={{ marginTop: 10 }}>
        <Bar label="Skills covered" value={b.skills_covered_score} />
        <Bar label="Role trend" value={b.role_trend_score} />
        <Bar label="Transferability" value={b.transferability_score} />
      </div>

      <p style={{ margin: "8px 0 4px" }}>
        <b>You have:</b>{" "}
        {role.matched_skills.length ? role.matched_skills.map(prettify).join(", ") : "none yet"}
      </p>
      <p style={{ margin: "4px 0" }}>
        <b>Skills gap:</b>{" "}
        {role.missing_skills.length ? role.missing_skills.map(prettify).join(", ") : "none"}
      </p>

      <p style={{ margin: "8px 0 4px", fontStyle: "italic" }}>{role.robustness_estimate}</p>

      <small style={{ opacity: 0.7 }}>
        Source: {role.source_badges.map((s) => `${s.source} (${s.date})`).join("; ")}
      </small>
    </div>
  );
}