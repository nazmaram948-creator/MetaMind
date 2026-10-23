import Icon from "./Icon";

export default function SkillPicker({ source, skills, chosen, setChosen, busy, onConfirm, onBack }) {
  const picked = skills.filter((s) => chosen[s.skill_id]).length;
  const toggle = (id) => setChosen({ ...chosen, [id]: !chosen[id] });
  const unsure = skills.filter((s) => s.status === "needs_confirmation").length;

  return (
    <>
      <p className="eyebrow">{source}</p>
      <h1 className="big">{skills.length} skills in your CV</h1>
      <div className="body">
        {skills.length === 0 ? (
          <p className="muted">Nothing in this text matched an ESCO skill. Try a longer CV or describe your daily tasks.</p>
        ) : (
          <div className="chips">
            {skills.map((s) => (
              <button key={s.skill_id} type="button"
                className={`chip${chosen[s.skill_id] ? " on" : ""}${s.status === "needs_confirmation" ? " ask" : ""}`}
                title={`Found in your CV: “${s.extracted_phrase}” · match ${Math.round(s.confidence * 100)}%`}
                onClick={() => toggle(s.skill_id)}>
                {chosen[s.skill_id] && <Icon name="check" size={13} stroke={2.2} />}
                {s.skill_name}
              </button>
            ))}
          </div>
        )}
        {skills.length > 0 && (
          <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
            {picked} selected to match you with roles. Tap a skill to remove or add it.
            {unsure > 0 && <span className="faint"> Dashed ones are weaker matches and start unselected.</span>}
          </p>
        )}
        <div className="controls">
          <button className="pill ghost" onClick={onBack}><Icon name="back" size={16} /> Back</button>
          <button className="pill white" disabled={!picked || busy} onClick={onConfirm}>
            {busy ? <span className="spin" /> : "Show my roles"}
          </button>
        </div>
      </div>
    </>
  );
}
