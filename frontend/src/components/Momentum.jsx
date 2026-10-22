import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Estimate, Source } from "./Badge";

const COLOR = { rising: "#e3ec6c", stable: "rgba(246,242,239,0.45)", declining: "#ff7066" };
const MAX_ROWS = 10;
const HINT = {
  moderate: "Automation counts once against a role's outlook (gamma = 1). Changes the chart and the role ranking.",
  fast: "Automation counts twice as hard against a role's outlook (gamma = 2): roles where AI mostly does the work fall further.",
};

function pick(signals) {
  const sorted = [...signals].sort((a, b) => b.value - a.value);
  if (sorted.length <= MAX_ROWS) return sorted;
  return [...sorted.slice(0, MAX_ROWS / 2), ...sorted.slice(-MAX_ROWS / 2)];
}

const cut = (s, n = 26) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const s = payload[0].payload;
  return (
    <div className="card" style={{ padding: "10px 14px", borderRadius: 14, fontSize: 12.5 }}>
      <div style={{ fontWeight: 500 }}>{s.name}</div>
      <div className="muted">momentum {s.value > 0 ? "+" : ""}{s.value} · {s.status}</div>
    </div>
  );
}

export default function Momentum({ signals, scenario, setScenario, mine }) {
  const rows = pick(signals);
  const badge = signals[0]?.source;
  return (
    <section className="card" id="momentum">
      <div className="chart-head">
        <p className="label" style={{ margin: 0 }}>{mine ? "Your skills, momentum" : "Skill momentum"}</p>
        <span className="adopt">
          <span className="faint">AI adoption</span>
          <div className="seg" role="group" aria-label="AI adoption speed">
            {["moderate", "fast"].map((s) => (
              <button key={s} className={scenario === s ? "on" : ""} onClick={() => setScenario(s)} title={HINT[s]}>
                {s === "moderate" ? "Moderate" : "Fast"}
              </button>
            ))}
          </div>
        </span>
      </div>
      <p className="faint scen-hint">{HINT[scenario]}</p>
      {rows.length === 0 ? <p className="skeleton">Loading…</p> : (
        <ResponsiveContainer width="100%" height={rows.length * 30 + 20}>
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <XAxis type="number" hide domain={["dataMin", "dataMax"]} />
            <YAxis type="category" dataKey="name" width={160} tickLine={false} axisLine={false}
              tick={{ fill: "rgba(246,242,239,0.7)", fontSize: 11.5 }} tickFormatter={(v) => cut(v, 24)} interval={0} />
            <ReferenceLine x={0} stroke="rgba(255,255,255,0.25)" />
            <Tooltip content={<Tip />} cursor={{ fill: "rgba(255,255,255,0.05)" }} />
            <Bar dataKey="value" radius={6} barSize={12}>
              {rows.map((r) => <Cell key={r.id} fill={COLOR[r.status]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
      <div className="legend" style={{ marginTop: 10 }}>
        <span><i className="dot" style={{ background: COLOR.rising }} />rising</span>
        <span><i className="dot" style={{ background: COLOR.stable }} />stable</span>
        <span><i className="dot" style={{ background: COLOR.declining }} />declining</span>
      </div>
      <div className="foot">
        <Source badge={badge} /><Estimate note="Momentum = outlook of the roles that need this skill" />
      </div>
      {signals.length > rows.length && (
        <p className="faint" style={{ fontSize: 11.5, margin: "8px 0 0" }}>
          Strongest {MAX_ROWS / 2} each way of {signals.length}.
        </p>
      )}
    </section>
  );
}
