import { useEffect, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Card, ChartTip, Legend, Loading, axisProps, useApi } from "../components/ui";
import { compact, dateLabel, money } from "../format";

const NEW_GOAL = () => ({
  name: "", target_amount: 500000, current_savings: 0, monthly_contribution: 10000,
  target_date: new Date(new Date().getFullYear() + 3, new Date().getMonth(), 1).toISOString().slice(0, 10),
  expected_return: 0.11, volatility: 0.15,
});

const PRESETS = [
  ["Savings account / FD", 0.065, 0.02],
  ["Debt mutual fund", 0.075, 0.04],
  ["Balanced (60% equity)", 0.10, 0.11],
  ["Equity index fund", 0.12, 0.17],
];

export default function Goals() {
  const [version, setVersion] = useState(0);
  const { data: goals, error } = useApi("/goals", [version]);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (goals && !selected) setSelected(goals[0] ?? NEW_GOAL());
  }, [goals, selected]);

  if (!goals || !selected) return <Loading error={error} />;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Goal planner</h1>
          <div className="subtle">Each plan runs 10,000 simulated market scenarios to give you a probability, not a promise.</div>
        </div>
        <button className="btn" onClick={() => setSelected(NEW_GOAL())}>New goal</button>
      </div>
      <div className="row" style={{ marginBottom: 16 }}>
        {goals.map((g) => (
          <button key={g.id} className={`btn ${selected.id === g.id ? "primary" : ""}`} onClick={() => setSelected(g)}>{g.name}</button>
        ))}
      </div>
      <Planner
        key={selected.id ?? "new"}
        goal={selected}
        onSaved={(g) => { setSelected(g); setVersion((v) => v + 1); }}
        onDeleted={() => { setSelected(null); setVersion((v) => v + 1); }}
      />
    </>
  );
}

function Planner({ goal, onSaved, onDeleted }) {
  const [g, setG] = useState(goal);
  const [sim, setSim] = useState(null);
  const [err, setErr] = useState("");
  const [running, setRunning] = useState(false);
  const set = (k, v) => setG((x) => ({ ...x, [k]: v }));
  const dirty = JSON.stringify(g) !== JSON.stringify(goal);

  // Re-run the simulation as inputs change (debounced so sliders feel smooth).
  useEffect(() => {
    const t = setTimeout(() => {
      setRunning(true);
      api("/goals/simulate", { method: "POST", body: { ...g, name: g.name || "Goal" } })
        .then((s) => { setSim(s); setErr(""); })
        .catch((e) => setErr(e.message))
        .finally(() => setRunning(false));
    }, 300);
    return () => clearTimeout(t);
  }, [g]);

  async function save() {
    const body = { ...g, name: g.name || "My goal" };
    const saved = g.id ? await api(`/goals/${g.id}`, { method: "PUT", body }) : await api("/goals", { method: "POST", body });
    onSaved(saved);
  }

  const start = new Date();
  const fan = sim?.fan.map((p) => ({ ...p, band: [p.p10, p.p90], date: new Date(start.getFullYear(), start.getMonth() + p.month, 1) })) ?? [];
  const prob = sim?.probability ?? 0;
  const verdict = prob >= 80 ? ["good", "On track"] : prob >= 50 ? ["warning", "Could go either way"] : ["critical", "Unlikely at this pace"];

  return (
    <div className="grid cols-3">
      <Card title={g.id ? "Plan" : "New goal"}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <label className="field">Goal name<input value={g.name} placeholder="e.g. Masters abroad" onChange={(e) => set("name", e.target.value)} /></label>
          <label className="field">Target amount (₹)<input type="number" min="1" value={g.target_amount} onChange={(e) => set("target_amount", Number(e.target.value))} /></label>
          <label className="field">Target date<input type="date" value={g.target_date} onChange={(e) => set("target_date", e.target.value)} /></label>
          <label className="field">Already saved (₹)<input type="number" min="0" value={g.current_savings} onChange={(e) => set("current_savings", Number(e.target.value))} /></label>
          <Slider label="Monthly investment" value={g.monthly_contribution} min={0} max={Math.max(100000, g.monthly_contribution)} step={500} fmt={money} onChange={(v) => set("monthly_contribution", v)} />
          <label className="field">Invested in
            <select
              value={PRESETS.findIndex(([, r, v]) => r === g.expected_return && v === g.volatility)}
              onChange={(e) => { const p = PRESETS[e.target.value]; if (p) setG((x) => ({ ...x, expected_return: p[1], volatility: p[2] })); }}
            >
              <option value={-1}>Custom</option>
              {PRESETS.map(([name], i) => <option key={name} value={i}>{name}</option>)}
            </select>
          </label>
          <Slider label="Expected annual return" value={g.expected_return} min={0} max={0.2} step={0.005} fmt={(v) => `${(v * 100).toFixed(1)}%`} onChange={(v) => set("expected_return", v)} />
          <Slider label="Volatility (risk)" value={g.volatility} min={0} max={0.35} step={0.01} fmt={(v) => `${Math.round(v * 100)}%`} onChange={(v) => set("volatility", v)} />
          <div className="row">
            <button className="btn primary" onClick={save} disabled={!dirty && g.id}>{g.id ? "Save changes" : "Save goal"}</button>
            {g.id && <button className="btn ghost" onClick={async () => { if (confirm("Delete this goal?")) { await api(`/goals/${g.id}`, { method: "DELETE" }); onDeleted(); } }}>Delete</button>}
          </div>
        </div>
      </Card>

      <div className="span-2" style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
        {err && <div className="notice error">{err}</div>}
        {sim && (
          <>
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
                <div>
                  <div className="subtle">Chance of reaching {money(g.target_amount)} by {dateLabel(g.target_date)}</div>
                  <div style={{ fontSize: 40, fontWeight: 700, letterSpacing: "-0.02em" }}>{sim.probability.toFixed(0)}%</div>
                  <span className="status"><span className={`dot ${verdict[0]}`} aria-hidden="true" />{verdict[1]}</span>
                </div>
                {running && <span className="spinner muted" />}
              </div>
              <div className="grid cols-3" style={{ marginTop: 16, gap: 12 }}>
                <div><div className="subtle" style={{ fontSize: 12.5 }}>Most likely outcome</div><b className="num">{money(sim.median_final)}</b></div>
                <div><div className="subtle" style={{ fontSize: 12.5 }}>Bad markets (10th percentile)</div><b className="num">{money(sim.p10_final)}</b></div>
                <div><div className="subtle" style={{ fontSize: 12.5 }}>You'll put in</div><b className="num">{money(sim.total_contributed)}</b></div>
              </div>
              {prob < 80 && (
                <div className="notice" style={{ marginTop: 14 }}>
                  Invest <b>{money(sim.required_monthly_80)}/month</b> for an 80% chance{" "}
                  <button className="btn small" style={{ marginLeft: 6 }} onClick={() => set("monthly_contribution", sim.required_monthly_80)}>Use this</button>
                </div>
              )}
            </div>
            <Card
              title="How your savings could grow"
              subtitle={`${sim.paths.toLocaleString("en-IN")} simulated scenarios. 8 in 10 land inside the shaded band.`}
              action={<Legend items={[["var(--series-1)", "Most likely"], ["var(--band)", "Likely range"], ["var(--muted)", "Money you put in", { height: 2, borderRadius: 0 }]]} />}
            >
              <div style={{ height: 280 }}>
                <ResponsiveContainer>
                  <ComposedChart data={fan}>
                    <CartesianGrid vertical={false} stroke="var(--grid)" />
                    <XAxis dataKey="date" tickFormatter={(d) => d.toLocaleDateString("en-IN", { month: "short", year: "2-digit" })} {...axisProps} minTickGap={40} />
                    <YAxis tickFormatter={compact} {...axisProps} axisLine={false} width={60} />
                    <Tooltip
                      cursor={{ stroke: "var(--axis)" }}
                      content={<ChartTip title={(d) => d.toLocaleDateString("en-IN", { month: "long", year: "numeric" })} rows={(r) => [
                        ["var(--series-1)", "Most likely", money(r.p50)],
                        ["var(--band)", "Range", `${compact(r.p10)} – ${compact(r.p90)}`],
                        ["var(--muted)", "Put in", money(r.contributed)],
                      ]} />}
                    />
                    <Area dataKey="band" stroke="none" fill="var(--band)" fillOpacity={0.7} isAnimationActive={false} activeDot={false} />
                    <Line dataKey="contributed" stroke="var(--muted)" strokeWidth={2} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
                    <Line dataKey="p50" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
                    <ReferenceLine y={g.target_amount} stroke="var(--text-2)" strokeDasharray="2 3" label={{ value: `Target ${compact(g.target_amount)}`, position: "insideTopLeft", fill: "var(--text-2)", fontSize: 12 }} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

function Slider({ label, value, min, max, step, fmt, onChange }) {
  return (
    <label className="field">
      <span className="row" style={{ justifyContent: "space-between" }}>{label}<b className="num" style={{ color: "var(--text)" }}>{fmt(value)}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} style={{ padding: 0, border: "none", accentColor: "var(--accent)" }} />
    </label>
  );
}
