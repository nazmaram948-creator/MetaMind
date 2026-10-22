import { useRef, useState } from "react";
import Icon from "./Icon";

const SAMPLES = {
  "SYN-001": "/samples/syn-001-aina.pdf",
  "SYN-002": "/samples/syn-002-faris.pdf",
  "SYN-003": "/samples/syn-003-kavitha.pdf",
  "USR-002": "/samples/usr-002-danial.pdf",
};

function OccupationSelect({ occupations, value, onChange }) {
  const groups = occupations.reduce((acc, o) => {
    (acc[o.family] ||= []).push(o);
    return acc;
  }, {});
  return (
    <select className="pill" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Current job">
      <option value="">No current job</option>
      {Object.entries(groups).map(([family, list]) => (
        <optgroup key={family} label={family[0].toUpperCase() + family.slice(1)}>
          {list.map((o) => <option key={o.occ_id} value={o.occ_id}>{o.title}</option>)}
        </optgroup>
      ))}
    </select>
  );
}

export default function Intake({ occupations, personas, busy, onSubmit, error }) {
  const [mode, setMode] = useState("upload");
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [occ, setOcc] = useState("");
  const [persona, setPersona] = useState(null);
  const [over, setOver] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const input = useRef(null);

  const pickFile = (f) => {
    if (!f) return;
    setFile(f);
    setPersona(null);
    setMode("upload");
  };

  const roleOf = (p) => p.current_role || "Fresh graduate";

  const choosePersona = (p) => {
    setPersona(p);
    setFile(null);
    setText(p.cv_text);
    setMode("paste");
    setDemoOpen(false);
    // same rule as uploads: the job comes from the dropdown, never from the profile
    onSubmit({ text: p.cv_text, occupation: occ, label: `Demo profile: ${roleOf(p).toLowerCase()}` });
  };

  const ready = mode === "upload" ? !!file : text.trim().length > 20;
  const short = 21 - text.trim().length;
  const title = persona ? roleOf(persona) : mode === "paste" ? "Paste a CV" : file ? file.name : "Drop a CV";

  return (
    <>
      <p className="eyebrow">Not stored. Age and gender are never read.</p>
      <h1 className="big">{title}</h1>

      <div className="body">
        {mode === "upload" ? (
          <label
            className={`drop${over ? " over" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setOver(true); }}
            onDragLeave={() => setOver(false)}
            onDrop={(e) => { e.preventDefault(); setOver(false); pickFile(e.dataTransfer.files[0]); }}
          >
            <Icon name="upload" size={22} />
            <span>
              <strong>{file ? "Replace file" : "Choose a PDF or .txt"}</strong> or drag it here
            </span>
            <input ref={input} type="file" accept=".pdf,.txt,application/pdf,text/plain"
              onChange={(e) => pickFile(e.target.files[0])} />
          </label>
        ) : (
          <textarea className="cv" value={text} placeholder="Paste your CV or describe what you do at work"
            onChange={(e) => { setText(e.target.value); setPersona(null); }} />
        )}

        <div className="controls">
          <OccupationSelect occupations={occupations} value={occ} onChange={setOcc} />
          <button className="pill white" disabled={!ready || busy}
            onClick={() => onSubmit(mode === "upload" ? { file, occupation: occ, label: file.name }
              : { text, occupation: occ, label: persona?.name || "Your CV" })}>
            {busy ? <span className="spin" /> : "Read my skills"}
          </button>
          {mode === "paste" && !ready && (
            <span className="faint hint" aria-live="polite">
              Add {short} more character{short === 1 ? "" : "s"}
            </span>
          )}
          <button className="linkish" onClick={() => setMode(mode === "upload" ? "paste" : "upload")}>
            {mode === "upload" ? "paste text instead" : "upload a file instead"}
          </button>
        </div>
        <p className="faint hint">Choose your current job for better matches. It applies to uploads, pasted text and demo profiles.</p>

        {error && <p className="error">{error}</p>}

        {personas.length > 0 && (
          <div className="demo">
            <button className="linkish" onClick={() => setDemoOpen(!demoOpen)} aria-expanded={demoOpen}>
              No CV at hand? Try a demo profile
            </button>
            {demoOpen && (
              <div className="demo-menu" role="menu">
                {personas.map((p) => (
                  <div key={p.id} className="demo-item">
                    <button role="menuitem" onClick={() => choosePersona(p)} disabled={busy}>
                      {roleOf(p)}{p.state ? `, ${p.state}` : ""}
                    </button>
                    {SAMPLES[p.id] && <a href={SAMPLES[p.id]} download title="Download this demo CV as a PDF">PDF</a>}
                  </div>
                ))}
                <p className="faint">Synthetic people, written for this demo.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
