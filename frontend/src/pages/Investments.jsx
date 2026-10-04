import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, Legend, Loading, StatTile, useApi } from "../components/ui";
import { compact, dateLabel, money, money2, pct } from "../format";

export default function Investments() {
  const [version, setVersion] = useState(0);
  const { data, error } = useApi("/investments", [version]);
  const refresh = () => setVersion((v) => v + 1);
  if (!data) return <Loading error={error} />;
  const anyStale = data.holdings.some((h) => !h.live);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Investments</h1>
          <div className="subtle">Live prices for NSE/BSE stocks (Yahoo Finance) and mutual fund NAVs (AMFI via mfapi.in).</div>
        </div>
      </div>

      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        <StatTile label="Current value" value={compact(data.value)} foot={money(data.value)} />
        <StatTile label="Invested" value={compact(data.invested)} foot={`${data.holdings.length} holdings`} />
        <StatTile label="Total gain" value={<span className={data.gain >= 0 ? "delta-good" : "delta-bad"}>{data.gain >= 0 ? "+" : ""}{compact(data.gain)}</span>} foot={`${data.gain >= 0 ? "+" : ""}${pct(data.gain_pct)} absolute`} />
        <StatTile label="XIRR" value={data.xirr == null ? "–" : pct(data.xirr)} foot="Annualised return, accounting for when you invested" />
      </div>

      {data.allocation.length > 0 && (
        <Card title="Allocation" action={<Legend items={data.allocation.map((a, i) => [`var(--series-${i + 1})`, `${a.name} ${pct((a.value / data.value) * 100, 0)}`])} />}>
          <div style={{ display: "flex", gap: 2, height: 14, borderRadius: 4, overflow: "hidden" }}>
            {data.allocation.map((a, i) => (
              <div key={a.name} title={`${a.name}: ${money(a.value)}`} style={{ flex: a.value, background: `var(--series-${i + 1})` }} />
            ))}
          </div>
        </Card>
      )}

      <Card title="Holdings" subtitle={anyStale ? "Some prices couldn't be fetched live, so the last known price is shown." : undefined} className="mt">
        {data.holdings.length === 0 ? <div className="empty">No holdings yet. Add your first one below.</div> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Holding</th><th className="right">Units</th><th className="right">Avg cost</th><th className="right">Price</th><th className="right">Value</th><th className="right">Gain</th><th className="right">XIRR</th><th /></tr>
              </thead>
              <tbody>
                {data.holdings.map((h) => (
                  <tr key={h.id}>
                    <td>
                      <div style={{ fontWeight: 550 }}>{h.name}</div>
                      <div className="muted" style={{ fontSize: 12 }}>{h.kind === "mf" ? "Mutual fund" : "Stock"} · {h.symbol} · since {dateLabel(h.purchase_date)}</div>
                    </td>
                    <td className="right num">{h.units}</td>
                    <td className="right num">{money2(h.avg_cost)}</td>
                    <td className="right num">
                      {money2(h.price)}
                      <div className="status" style={{ display: "flex", justifyContent: "flex-end", fontSize: 11.5 }}>
                        <span className={`dot ${h.live ? "good" : "warning"}`} aria-hidden="true" />{h.live ? "Live" : "Last known"}
                      </div>
                    </td>
                    <td className="right num">{money(h.value)}</td>
                    <td className={`right num ${h.gain >= 0 ? "delta-good" : "delta-bad"}`}>{h.gain >= 0 ? "+" : ""}{money(h.gain)}<div style={{ fontSize: 12 }}>{pct(h.gain_pct)}</div></td>
                    <td className="right num">{h.xirr == null ? "–" : pct(h.xirr)}</td>
                    <td className="right"><button className="btn small ghost" aria-label="Remove" onClick={async () => { if (confirm(`Remove ${h.name}?`)) { await api(`/investments/${h.id}`, { method: "DELETE" }); refresh(); } }}>✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <AddHolding onAdded={refresh} />
      </Card>
    </>
  );
}

function AddHolding({ onAdded }) {
  const blank = { kind: "stock", symbol: "", name: "", units: "", avg_cost: "", purchase_date: "" };
  const [f, setF] = useState(blank);
  const [results, setResults] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (f.kind !== "mf" || f.name.length < 3 || f.symbol) return setResults([]);
    const t = setTimeout(() => api(`/investments/search-mf?q=${encodeURIComponent(f.name)}`).then(setResults).catch(() => {}), 350);
    return () => clearTimeout(t);
  }, [f.kind, f.name, f.symbol]);

  async function submit(e) {
    e.preventDefault();
    setErr("");
    try {
      await api("/investments", { method: "POST", body: { ...f, units: Number(f.units), avg_cost: Number(f.avg_cost), name: f.name || f.symbol } });
      setF(blank);
      onAdded();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <form onSubmit={submit} style={{ marginTop: 18, borderTop: "1px solid var(--grid)", paddingTop: 16 }}>
      <h3>Add a holding</h3>
      <div className="form-grid">
        <label className="field">Type
          <select value={f.kind} onChange={(e) => setF({ ...blank, kind: e.target.value })}>
            <option value="stock">Stock</option><option value="mf">Mutual fund</option>
          </select>
        </label>
        {f.kind === "stock" ? (
          <>
            <label className="field">NSE symbol<input required placeholder="INFY.NS" value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })} /></label>
            <label className="field">Name<input placeholder="Infosys" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
          </>
        ) : (
          <label className="field" style={{ gridColumn: "span 2", position: "relative" }}>Fund name (search) or AMFI code
            <input required placeholder="Parag Parikh Flexi Cap" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value, symbol: "" })} />
            {results.length > 0 && (
              <div className="card" style={{ position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10, padding: 4, maxHeight: 240, overflowY: "auto" }}>
                {results.map((r) => (
                  <button type="button" key={r.code} className="btn ghost small" style={{ width: "100%", justifyContent: "flex-start", whiteSpace: "normal", textAlign: "left" }} onClick={() => setF({ ...f, symbol: r.code, name: r.name })}>
                    {r.name}
                  </button>
                ))}
              </div>
            )}
            {f.symbol ? <span className="muted" style={{ fontSize: 12 }}>Scheme code {f.symbol}</span> : (
              <input placeholder="or scheme code, e.g. 122639" value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })} style={{ marginTop: 4 }} />
            )}
          </label>
        )}
        <label className="field">Units<input type="number" step="any" min="0" required value={f.units} onChange={(e) => setF({ ...f, units: e.target.value })} /></label>
        <label className="field">Avg buy price (₹)<input type="number" step="any" min="0" required value={f.avg_cost} onChange={(e) => setF({ ...f, avg_cost: e.target.value })} /></label>
        <label className="field">Bought on<input type="date" required value={f.purchase_date} onChange={(e) => setF({ ...f, purchase_date: e.target.value })} /></label>
        <div><button className="btn primary" type="submit">Add holding</button></div>
      </div>
      {err && <div className="notice error" style={{ marginTop: 10 }}>{err}</div>}
    </form>
  );
}
