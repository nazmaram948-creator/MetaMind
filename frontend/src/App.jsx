import { useState } from "react";
import { parseProfile, matchRoles } from "./api";
import RoleCard from "./RoleCard";

export default function App() {
  const [text, setText] = useState("I use Excel for data analysis");
  const [skills, setSkills] = useState([]);
  const [chosen, setChosen] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleParse() {
    try {
      setError("");
      const data = await parseProfile("office_clerk", text);
            setSkills(data.skills);
      setResult(null);
      setChosen(Object.fromEntries(data.skills.map((s) => [s.skill_id, true])));
      if (data.skills.length === 0) {
        setError("No skills recognised. Try mentioning skills like data analysis, spreadsheets, project management or customer service.");
      }
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleMatch() {
    const ids = skills.filter((s) => chosen[s.skill_id]).map((s) => s.skill_id);
    try {
      setError("");
      setResult(await matchRoles(ids));
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div style={{ maxWidth: 700, margin: "2rem auto", fontFamily: "sans-serif" }}>
      <h1>Future Skills Compass</h1>

      <h2>1. Tell us about yourself</h2>
      <textarea rows={4} style={{ width: "100%" }} value={text}
        onChange={(e) => setText(e.target.value)} />
      <button onClick={handleParse}>Extract skills</button>

      {skills.length > 0 && (
        <>
          <h2>2. Confirm your skills</h2>
          {skills.map((s) => (
            <label key={s.skill_id} style={{ display: "block" }}>
              <input type="checkbox" checked={!!chosen[s.skill_id]}
                onChange={() => setChosen({ ...chosen, [s.skill_id]: !chosen[s.skill_id] })} />
              {s.skill_name} (found: "{s.extracted_phrase}")
            </label>
          ))}
          <button onClick={handleMatch}>Find my roles</button>
        </>
      )}

      {error && <p style={{ color: "red" }}>{error}</p>}

      {result && (
        <>
          <h2>3. Your roles (Estimate)</h2>
          {result.roles.map((r, i) => (
            <RoleCard key={r.role_id} role={r} rank={i + 1} />
          ))}
          <small>{result.assumption_note}</small>
        </>
      )}
    </div>
  );
}