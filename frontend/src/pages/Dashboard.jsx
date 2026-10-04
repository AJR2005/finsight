import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Card, ChartTip, Legend, Loading, StatTile, axisProps, useApi } from "../components/ui";
import { compact, dateLabel, money, monthLabel, pct } from "../format";

export default function Dashboard({ me, onMeChange }) {
  const { data, error, reload } = useApi("/dashboard");
  if (!data) return <Loading error={error} />;

  const change = data.last_month_spend ? (data.month_spend / data.last_month_spend - 1) * 100 : null;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Hi {me?.name?.split(" ")[0] ?? "there"}</h1>
          <div className="subtle">{data.empty ? "Let's get your money organised." : `Here's ${monthLabel(data.month, true)} so far.`}</div>
        </div>
        <Link className="btn primary" to="/transactions">Upload statement</Link>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <StatTile
          label="Net worth"
          value={compact(data.net_worth)}
          foot={<CashBalance value={data.cash_balance} investments={data.investments} onSaved={(m) => { onMeChange(m); reload(); }} />}
        />
        <StatTile
          label="Spent this month"
          value={money(data.month_spend ?? 0)}
          foot={change == null ? "Excludes investments and transfers" : `Last month: ${money(data.last_month_spend)}`}
        />
        <StatTile label="Income this month" value={money(data.month_income ?? 0)} foot="Salary and other income" />
        <StatTile
          label="Savings rate (12 months)"
          value={pct(data.savings_rate_12m ?? 0)}
          foot={<span className={(data.savings_rate_12m ?? 0) >= 20 ? "delta-good" : "delta-bad"}>{(data.savings_rate_12m ?? 0) >= 20 ? "Above the 20% rule of thumb" : "Below the 20% rule of thumb"}</span>}
        />
      </div>

      {data.empty ? (
        <Card>
          <div className="empty">
            <h2 style={{ marginBottom: 6 }}>No transactions yet</h2>
            <p>Upload a CSV, Excel or PDF statement from your bank and FinSight will categorise it automatically.</p>
            <Link className="btn primary" to="/transactions">Upload your first statement</Link>
          </div>
        </Card>
      ) : (
        <>
          <Card title="Income vs spending" subtitle="Last 12 months. Spending excludes investments and transfers." action={<Legend items={[["var(--series-1)", "Income"], ["var(--series-2)", "Spending"]]} />}>
            <div style={{ height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={data.monthly} barGap={2} barCategoryGap="24%">
                  <CartesianGrid vertical={false} stroke="var(--grid)" />
                  <XAxis dataKey="month" tickFormatter={(m) => monthLabel(m)} {...axisProps} />
                  <YAxis tickFormatter={compact} {...axisProps} axisLine={false} width={56} />
                  <Tooltip
                    cursor={{ fill: "var(--surface-2)" }}
                    content={<ChartTip title={(m) => monthLabel(m, true)} rows={(r) => [
                      ["var(--series-1)", "Income", money(r.income)],
                      ["var(--series-2)", "Spending", money(r.spend)],
                      [null, "Saved", money(r.savings)],
                    ]} />}
                  />
                  <Bar isAnimationActive={false} dataKey="income" name="Income" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={22} />
                  <Bar isAnimationActive={false} dataKey="spend" name="Spending" fill="var(--series-2)" radius={[4, 4, 0, 0]} maxBarSize={22} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <div className="grid cols-2" style={{ marginTop: 16 }}>
            <Card title="Where it went this month" subtitle="The tick marks last month's total for each category.">
              <CategoryBars rows={data.categories} />
            </Card>
            <Card title="Top merchants" subtitle="Last 90 days">
              <table>
                <tbody>
                  {data.top_merchants.map((m) => (
                    <tr key={m.merchant}>
                      <td>{m.merchant}</td>
                      <td className="muted">{m.count}×</td>
                      <td className="right num">{money(m.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>

          <Card title="Recent transactions" action={<Link to="/transactions">View all</Link>} className="mt">
            <div className="table-wrap">
              <table>
                <tbody>
                  {data.recent.map((t) => (
                    <tr key={t.id}>
                      <td className="muted" style={{ whiteSpace: "nowrap" }}>{dateLabel(t.date)}</td>
                      <td className="desc" title={t.description}>{t.description}</td>
                      <td><span className="badge">{t.category}</span></td>
                      <td className={`right num ${t.amount > 0 ? "delta-good" : ""}`}>{t.amount > 0 ? "+" : ""}{money(t.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </>
  );
}

function CategoryBars({ rows }) {
  if (!rows.length) return <div className="muted">Nothing spent yet this month.</div>;
  const max = Math.max(...rows.map((r) => Math.max(r.amount, r.last_month)));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {rows.slice(0, 8).map((r) => (
        <div key={r.category} title={`Last month: ${money(r.last_month)}`}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: 4 }}>
            <span>{r.category}</span>
            <span className="num">{money(r.amount)}</span>
          </div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(r.amount / max) * 100}%` }} />
            {r.last_month > 0 && <div className="bar-marker" style={{ left: `calc(${(r.last_month / max) * 100}% - 1px)` }} />}
          </div>
        </div>
      ))}
    </div>
  );
}

function CashBalance({ value, investments, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState(value);
  if (!editing)
    return (
      <span>
        {compact(value)} bank + {compact(investments)} invested ·{" "}
        <a href="#" onClick={(e) => { e.preventDefault(); setV(value); setEditing(true); }}>edit</a>
      </span>
    );
  return (
    <form
      className="row"
      style={{ gap: 6 }}
      onSubmit={async (e) => {
        e.preventDefault();
        const me = await api("/me", { method: "PATCH", body: { cash_balance: Number(v) } });
        setEditing(false);
        onSaved(me);
      }}
    >
      <input type="number" value={v} onChange={(e) => setV(e.target.value)} style={{ width: 110, padding: "3px 6px" }} aria-label="Bank balance" autoFocus />
      <button className="btn small" type="submit">Save</button>
    </form>
  );
}
