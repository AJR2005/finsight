import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Card, ChartTip, Legend, Loading, StatTile, Status, axisProps, useApi } from "../components/ui";
import { compact, dateLabel, money, monthLabel, pct } from "../format";

export default function Insights() {
  const [version, setVersion] = useState(0);
  const forecast = useApi("/insights/forecast", [version]);
  const anomalies = useApi("/insights/anomalies");
  const subs = useApi("/insights/subscriptions", [version]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Forecast & budgets</h1>
          <div className="subtle">What you're likely to spend, where you'll overshoot, and charges worth a second look.</div>
        </div>
      </div>
      {forecast.data ? <Forecast f={forecast.data} onBudgetChange={() => setVersion((v) => v + 1)} /> : <Loading error={forecast.error} />}
      <div className="grid cols-2" style={{ marginTop: 16 }}>
        <Card title="Unusual charges" subtitle="Payments far above what's normal for their category.">
          {anomalies.data ? <Anomalies items={anomalies.data} /> : <Loading error={anomalies.error} />}
        </Card>
        <Card title="Recurring payments" subtitle="Subscriptions and bills found in your statements.">
          {subs.data ? <Subscriptions data={subs.data} onReviewed={() => setVersion((v) => v + 1)} /> : <Loading error={subs.error} />}
        </Card>
      </div>
    </>
  );
}

function Forecast({ f, onBudgetChange }) {
  const chart = f.history.map((h) => ({ month: h.month, spend: h.spend }));
  if (chart.length) {
    chart[chart.length - 1].forecast = chart[chart.length - 1].spend;
    chart[chart.length - 1].range = [chart[chart.length - 1].spend, chart[chart.length - 1].spend];
  }
  chart.push({ month: f.forecast_month, forecast: f.forecast_total, range: [f.forecast_low, f.forecast_high], isForecast: true });

  return (
    <>
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <StatTile label={`Forecast spend, ${monthLabel(f.forecast_month, true)}`} value={money(f.forecast_total)} foot={`Likely between ${compact(f.forecast_low)} and ${compact(f.forecast_high)}`} />
        <StatTile label="Projected savings" value={<span className={f.projected_savings >= 0 ? "" : "delta-bad"}>{money(f.projected_savings)}</span>} foot={`Expected income ${money(f.forecast_income)}`} />
        <StatTile label="Forecast error (backtest)" value={f.backtest_mape == null ? "–" : pct(f.backtest_mape)} foot="Average miss over the last 3 months" />
        <StatTile label="Model chosen" value={<span style={{ fontSize: 16 }}>{f.method}</span>} foot={`Lowest backtest error on your data${f.excluded_one_offs ? `; ${f.excluded_one_offs} one-off purchases left out` : ""}`} />
      </div>
      <div className="grid cols-2">
        <Card
          title="Monthly spending and forecast"
          subtitle="Shaded band is the likely range (80% interval)."
          action={<Legend items={[["var(--series-1)", "Actual"], ["var(--series-2)", "Forecast"]]} />}
        >
          <div style={{ height: 260 }}>
            <ResponsiveContainer>
              <ComposedChart data={chart}>
                <CartesianGrid vertical={false} stroke="var(--grid)" />
                <XAxis dataKey="month" tickFormatter={(m) => monthLabel(m)} {...axisProps} />
                <YAxis tickFormatter={compact} {...axisProps} axisLine={false} width={56} domain={[0, "auto"]} />
                <Tooltip
                  cursor={{ stroke: "var(--axis)" }}
                  content={<ChartTip title={(m) => monthLabel(m, true)} rows={(r) => r.isForecast
                    ? [["var(--series-2)", "Forecast", money(r.forecast)], [null, "Range", `${compact(r.range[0])} – ${compact(r.range[1])}`]]
                    : [["var(--series-1)", "Spent", money(r.spend)]]} />}
                />
                <Area dataKey="range" stroke="none" fill="var(--series-2)" fillOpacity={0.18} isAnimationActive={false} activeDot={false} />
                <Line isAnimationActive={false} dataKey="spend" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3, strokeWidth: 0, fill: "var(--series-1)" }} activeDot={{ r: 5 }} />
                <Line isAnimationActive={false} dataKey="forecast" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="5 4" dot={(p) => p.payload.isForecast ? <circle key="f" cx={p.cx} cy={p.cy} r={5} fill="var(--series-2)" stroke="var(--surface)" strokeWidth={2} /> : <g key={p.index} />} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Budgets rows={f.budgets} progress={f.month_progress} typical={f.by_category} onChange={onBudgetChange} />
      </div>
    </>
  );
}

function Budgets({ rows, progress, typical, onChange }) {
  const categories = useApi("/categories").data ?? [];
  const budgetList = useApi("/budgets", [rows.length]).data ?? [];
  const [form, setForm] = useState({ category: "", monthly_limit: "" });

  async function save(e) {
    e.preventDefault();
    await api("/budgets", { method: "PUT", body: { category: form.category, monthly_limit: Number(form.monthly_limit) } });
    setForm({ category: "", monthly_limit: "" });
    onChange();
  }
  async function remove(category) {
    const b = budgetList.find((x) => x.category === category);
    if (b) await api(`/budgets/${b.id}`, { method: "DELETE" });
    onChange();
  }

  return (
    <Card title="Budgets this month" subtitle={`${Math.round(progress * 100)}% of the month gone. Bar is spent so far; the tick is where you're heading.`}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {rows.length === 0 && <div className="muted">No budgets yet. Add one below.</div>}
        {rows.map((b) => {
          const scale = Math.max(b.limit, b.projected) * 1.05;
          const tone = b.status === "over" ? "critical" : b.status === "at_risk" ? "warning" : "";
          return (
            <div key={b.category}>
              <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
                <span><b style={{ fontWeight: 600 }}>{b.category}</b> <span className="muted num">{money(b.spent)} of {money(b.limit)}</span></span>
                <span className="row" style={{ gap: 8 }}>
                  <Status value={b.status} />
                  <button className="btn small ghost" onClick={() => remove(b.category)} aria-label={`Remove ${b.category} budget`}>✕</button>
                </span>
              </div>
              <div className="bar-track" title={`Projected: ${money(b.projected)}`}>
                <div className={`bar-fill ${tone}`} style={{ width: `${Math.min(b.spent / scale, 1) * 100}%` }} />
                <div className="bar-marker" style={{ left: `calc(${(b.projected / scale) * 100}% - 1px)` }} />
                <div className="bar-marker" style={{ left: `calc(${(b.limit / scale) * 100}% - 1px)`, background: "var(--critical)", opacity: 0.6 }} />
              </div>
              <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>Heading for {money(b.projected)}</div>
            </div>
          );
        })}
      </div>
      <form className="row" onSubmit={save} style={{ marginTop: 16 }}>
        <select required value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value, monthly_limit: form.monthly_limit || Math.round((typical[e.target.value] ?? 0) / 100) * 100 || "" })} aria-label="Category">
          <option value="">Category…</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
        <input type="number" min="1" required placeholder="Monthly limit ₹" value={form.monthly_limit} onChange={(e) => setForm({ ...form, monthly_limit: e.target.value })} style={{ width: 150 }} />
        <button className="btn" type="submit">Set budget</button>
      </form>
    </Card>
  );
}

function Anomalies({ items }) {
  if (!items.length) return <div className="muted">Nothing unusual in the last 90 days.</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {items.map((a) => (
        <div key={a.id} className="notice" style={{ display: "flex", justifyContent: "space-between", gap: 12, color: "var(--text)" }}>
          <div style={{ minWidth: 0 }}>
            <div className="desc" title={a.description} style={{ fontWeight: 550 }}>{a.description}</div>
            <div className="subtle" style={{ fontSize: 12.5 }}>{dateLabel(a.date)} · {a.category} · usually {money(a.typical)}</div>
          </div>
          <div style={{ textAlign: "right", whiteSpace: "nowrap" }}>
            <div className="num" style={{ fontWeight: 650 }}>{money(a.amount)}</div>
            <div className="delta-bad" style={{ fontSize: 12.5 }}>{a.times_typical}× usual</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Subscriptions({ data, onReviewed }) {
  if (!data.items.length) return <div className="muted">No recurring payments found yet. They appear after 3 or more charges.</div>;
  return (
    <>
      <div className="row" style={{ gap: 24, marginBottom: 12 }}>
        <div><div className="subtle" style={{ fontSize: 12.5 }}>Active, per month</div><b className="num" style={{ fontSize: 18 }}>{money(data.monthly_total)}</b></div>
        <div><div className="subtle" style={{ fontSize: 12.5 }}>Per year</div><b className="num" style={{ fontSize: 18 }}>{money(data.annual_total)}</b></div>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Merchant</th><th>Every</th><th className="right">Amount</th><th>Next</th><th /></tr></thead>
          <tbody>
            {data.items.map((s) => (
              <tr key={s.merchant} style={{ opacity: s.active ? 1 : 0.55 }}>
                <td style={{ textTransform: "capitalize" }}>
                  {s.merchant}
                  <div className="muted" style={{ fontSize: 12 }}>{s.category}{s.price_change > 0 ? ` · price up ${money(s.price_change)}` : ""}</div>
                </td>
                <td>{s.period.replace("ly", "")}</td>
                <td className="right num">{money(s.amount)}</td>
                <td className="muted" style={{ whiteSpace: "nowrap" }}>{s.active ? dateLabel(s.next_due) : "Stopped"}</td>
                <td className="right">
                  {s.active && !s.reviewed ? (
                    <button className="btn small" onClick={async () => { await api(`/insights/subscriptions/${encodeURIComponent(s.merchant)}/review`, { method: "POST" }); onReviewed(); }}>Still need it</button>
                  ) : s.reviewed ? <span className="badge">Reviewed</span> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
