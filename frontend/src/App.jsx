import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import Icon from "./components/Icon";
import Intake from "./components/Intake";
import SkillPicker from "./components/SkillPicker";
import Momentum from "./components/Momentum";
import { MalaysiaTile, SafestTile } from "./components/Tiles";
import Roles from "./components/Roles";
import DiffCard from "./components/DiffCard";

function Stat({ n, k, color, fill }) {
  return (
    <div className="stat">
      <div className="n">{n}</div>
      <div className="k"><i className="dot" style={{ background: color }} />{k}</div>
      <div className="bar"><i style={{ width: `${Math.max(0, Math.min(1, fill)) * 100}%` }} /></div>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [occupations, setOccupations] = useState([]);
  const [personas, setPersonas] = useState([]);
  const [ctx, setCtx] = useState(null);
  const [catalog, setCatalog] = useState([]);

  const [stage, setStage] = useState("intake");
  const [source, setSource] = useState("");
  const [current, setCurrent] = useState("");
  const [skills, setSkills] = useState([]);
  const [chosen, setChosen] = useState({});
  const [scenario, setScenario] = useState("moderate");

  const [snap, setSnap] = useState({ id: "baseline_snapshot", label: "", baseLabel: "" });
  const [result, setResult] = useState(null);
  const [mine, setMine] = useState([]);
  const [diff, setDiff] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const selected = skills.filter((s) => chosen[s.skill_id]).map((s) => s.skill_id);
  const occTitle = occupations.find((o) => o.occ_id === current)?.title;

  const run = useCallback(async (label, fn) => {
    setBusy(label);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }, []);

  // first load: data that needs no CV, and a known snapshot on the server
  useEffect(() => {
    (async () => {
      try {
        const h = await api.getHealth();
        setHealth(h);
        if (h.mode !== "engine") return;
        const base = await api.loadSnapshot("baseline_snapshot");
        setSnap({ id: "baseline_snapshot", label: base.metadata.label, baseLabel: base.metadata.label });
        const [occ, ppl, c, cat] = await Promise.all([
          api.getOccupations(), api.getPersonas(), api.getContext(), api.getSignals([], "moderate"),
        ]);
        setOccupations(occ);
        setPersonas(ppl.individual_users);
        setCtx(c);
        setCatalog(cat);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const analyse = useCallback(async (ids, occ, scen, withDiff) => {
    const [m, sig, d] = await Promise.all([
      api.matchRoles(ids, occ, scen),
      api.getSignals(ids, scen),
      withDiff ? api.diffSnapshots(ids, occ, scen) : Promise.resolve(null),
    ]);
    setResult(m);
    setMine(sig);
    setDiff(d);
  }, []);

  // recompute whatever is on screen for a scenario / snapshot
  const refresh = (scen, latestData) =>
    result ? analyse(selected, current, scen, latestData) : api.getSignals([], scen).then(setCatalog);

  const changeScenario = (scen) => {
    setScenario(scen);
    run("match", () => refresh(scen, snap.id === "latest_snapshot"));
  };

  const onSubmit = ({ file, text, occupation, label }) =>
    run("parse", async () => {
      const out = file ? await api.parseFile(file, occupation) : await api.parseProfile(text, occupation);
      setSkills(out.skills);
      setChosen(Object.fromEntries(out.skills.map((s) => [s.skill_id, s.status === "suggested"])));
      setSource(label);
      setCurrent(occupation || "");
      setResult(null);
      setDiff(null);
      setStage("confirm");
    });

  const onConfirm = () =>
    run("match", async () => {
      await analyse(selected, current, scenario, snap.id === "latest_snapshot");
      setStage("results");
      setTimeout(() => document.getElementById("roles")?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    });

  const switchSnapshot = (id) =>
    run("snapshot", async () => {
      const out = await api.loadSnapshot(id);
      setSnap((s) => ({ ...s, id, label: out.metadata.label }));
      setCtx(await api.getContext());
      await refresh(scenario, id === "latest_snapshot");
    });

  const reset = () => {
    setStage("intake");
    setResult(null);
    setDiff(null);
    setSkills([]);
  };

  const latest = snap.id === "latest_snapshot";
  const movements = diff && Object.fromEntries(diff.changes.map((c) => [c.role_id, c.movement]));
  const top = result?.roles[0];
  const safest = result?.roles.find((r) => r.robustness.safest_pick);
  const rising = mine.filter((s) => s.status === "rising").length;

  return (
    <div className="shell">
      <nav className="rail" aria-label="Sections">
        <Icon name="logo" size={36} className="logo" />
        <a href="#top" className={stage !== "results" ? "on" : ""} title="Your CV"><Icon name="user" /></a>
        <a href="#momentum" title="Skill momentum"><Icon name="pulse" /></a>
        <a href="#roles" className={stage === "results" ? "on" : ""} title="Roles"><Icon name="list" /></a>
        <span className="spacer" />
        <a href="#sources" title="Sources"><Icon name="info" /></a>
      </nav>

      <main id="top">
        <header className="top">
          <h1 className="brand">SkillShift <span>MY</span></h1>
          {health?.mode === "engine" && (
            <div className="top-actions">
              <span className="pill small" title="Anthropic Economic Index snapshot in use">{snap.label || "…"}</span>
              {latest ? (
                <button className="pill small ghost" onClick={() => switchSnapshot("baseline_snapshot")} disabled={!!busy}>
                  Back to {snap.baseLabel}
                </button>
              ) : (
                <button className="pill small orange" onClick={() => switchSnapshot("latest_snapshot")} disabled={!!busy}>
                  {busy === "snapshot" ? <span className="spin" /> : <Icon name="refresh" size={16} />} Load newer data
                </button>
              )}
            </div>
          )}
        </header>

        {health && health.mode !== "engine" && (
          <div className="warn">
            The backend is running on demo fixtures. Start it with <code>ENGINE_MODE=true</code> to use real data.
          </div>
        )}
        {!health && error && <div className="warn">Can't reach the backend: {error}</div>}

        <div className="grid">
          <section className="card hero">
            {stage === "intake" ? (
              <Intake occupations={occupations} personas={personas} busy={busy === "parse"}
                onSubmit={onSubmit} error={error} />
            ) : (
              <SkillPicker source={`${source}${occTitle ? ` · now ${occTitle}` : " · no current job"}`}
                skills={skills} chosen={chosen} setChosen={setChosen} busy={busy === "match"}
                onConfirm={onConfirm} onBack={reset} />
            )}
            {stage !== "intake" && error && <p className="error" style={{ marginTop: 10 }}>{error}</p>}

            <div className="stats">
              {result ? (
                <>
                  <Stat n={selected.length} k="skills used for matching" color="var(--lime)" fill={selected.length / 30} />
                  <Stat n={top.total_match_score.toFixed(0)} k={`best: ${top.role_title}`} color="var(--orange)" fill={top.total_match_score / 100} />
                  <Stat n={`${mine.length ? Math.round((100 * rising) / mine.length) : 0}%`} k="of your skills rising" color="var(--sky)" fill={mine.length ? rising / mine.length : 0} />
                  <Stat n={ctx?.malaysia_usage_index?.toFixed(2) ?? "–"} k="Malaysia AI index" color="var(--coral)" fill={(ctx?.malaysia_usage_index || 0) / 1.5} />
                </>
              ) : (
                <>
                  <Stat n={occupations.length || "–"} k="roles mapped" color="var(--lime)" fill={1} />
                  <Stat n={skills.length || "–"} k="skills found in CV" color="var(--orange)" fill={skills.length / 30} />
                  <Stat n="1,000" k="futures per role" color="var(--sky)" fill={1} />
                  <Stat n={ctx?.malaysia_usage_index?.toFixed(2) ?? "–"} k="Malaysia AI index" color="var(--coral)" fill={(ctx?.malaysia_usage_index || 0) / 1.5} />
                </>
              )}
            </div>
          </section>

          <div className="stack">
            <Momentum signals={result ? mine : catalog} mine={!!result} scenario={scenario} setScenario={changeScenario} />
            <div className="row2">
              <MalaysiaTile ctx={ctx} />
              <SafestTile role={safest} note={result?.assumption_note} />
            </div>
          </div>
        </div>

        {diff && (
          <div style={{ marginTop: 22 }}>
            <DiffCard diff={diff} labels={{ from: snap.baseLabel, to: snap.label }} busy={!!busy}
              onUndo={() => switchSnapshot("baseline_snapshot")} />
          </div>
        )}

        {result && (
          <div style={{ marginTop: 22 }}>
            <Roles result={result} movements={movements} current={occTitle} />
          </div>
        )}

        <footer id="sources">
          <a href="https://huggingface.co/datasets/Anthropic/EconomicIndex" target="_blank" rel="noreferrer">Anthropic Economic Index (CC-BY)</a>
          <a href="https://www.onetcenter.org/database.html" target="_blank" rel="noreferrer">O*NET 31.0 (CC BY 4.0)</a>
          <a href="https://esco.ec.europa.eu/" target="_blank" rel="noreferrer">ESCO v1.2, European Commission</a>
          <span>Personas are synthetic. Rankings and momentum are estimates, not forecasts of jobs.</span>
        </footer>
      </main>
    </div>
  );
}
