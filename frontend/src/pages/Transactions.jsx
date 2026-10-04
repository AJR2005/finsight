import { useRef, useState } from "react";
import { api } from "../api";
import { Card, Loading, useApi } from "../components/ui";
import { dateLabel, money2, pct } from "../format";

const PAGE = 50;

export default function Transactions() {
  const [filters, setFilters] = useState({ month: "", category: "", q: "", needs_review: false });
  const [page, setPage] = useState(0);
  const [version, setVersion] = useState(0);
  const [toast, setToast] = useState(null);
  const categories = useApi("/categories").data ?? [];
  const metrics = useApi("/model/metrics", [version]).data;

  const params = new URLSearchParams({ limit: PAGE, offset: page * PAGE });
  Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));
  const { data, error } = useApi(`/transactions?${params}`, [version]);
  const refresh = () => setVersion((v) => v + 1);
  const setFilter = (k, v) => { setFilters({ ...filters, [k]: v }); setPage(0); };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Transactions</h1>
          <div className="subtle">Every transaction is categorised by a machine-learning model. Fix a category and the model retrains on your correction.</div>
        </div>
      </div>

      <div className="grid cols-3" style={{ marginBottom: 16 }}>
        <Upload onDone={(msg) => { setToast(msg); refresh(); }} />
        <ModelCard metrics={metrics} onReview={() => setFilter("needs_review", true)} />
      </div>

      {toast && (
        <div className="notice" style={{ marginBottom: 12, display: "flex", justifyContent: "space-between", gap: 12 }}>
          <span>{toast}</span>
          <button className="btn small ghost" onClick={() => setToast(null)} aria-label="Dismiss">✕</button>
        </div>
      )}

      <Card>
        <div className="row" style={{ marginBottom: 12 }}>
          <input placeholder="Search description" value={filters.q} onChange={(e) => setFilter("q", e.target.value)} style={{ flex: "1 1 200px" }} />
          <input type="month" value={filters.month} onChange={(e) => setFilter("month", e.target.value)} aria-label="Month" />
          <select value={filters.category} onChange={(e) => setFilter("category", e.target.value)} aria-label="Category">
            <option value="">All categories</option>
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          <label className="row" style={{ gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={filters.needs_review} onChange={(e) => setFilter("needs_review", e.target.checked)} />
            Needs review only
          </label>
          <AddTransaction categories={categories} onAdded={refresh} />
        </div>

        {!data ? <Loading error={error} /> : data.items.length === 0 ? (
          <div className="empty">No transactions match these filters.</div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Date</th><th>Description</th><th>Category</th><th title="Model confidence">Confidence</th><th className="right">Amount</th><th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((t) => (
                    <Row key={t.id} t={t} categories={categories} onChanged={(msg) => { setToast(msg); refresh(); }} />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="row" style={{ justifyContent: "space-between", marginTop: 12 }}>
              <span className="muted">{data.total} transactions</span>
              <span className="row">
                <button className="btn small" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
                <span className="muted">Page {page + 1} of {Math.max(1, Math.ceil(data.total / PAGE))}</span>
                <button className="btn small" disabled={(page + 1) * PAGE >= data.total} onClick={() => setPage(page + 1)}>Next</button>
              </span>
            </div>
          </>
        )}
      </Card>
    </>
  );
}

function Row({ t, categories, onChanged }) {
  const [busy, setBusy] = useState(false);
  async function change(category) {
    setBusy(true);
    try {
      const r = await api(`/transactions/${t.id}/category`, { method: "PATCH", body: { category, apply_to_similar: true } });
      const extra = r.updated_similar ? ` and ${r.updated_similar} similar transaction${r.updated_similar > 1 ? "s" : ""}` : "";
      onChanged(`Saved "${category}" for this${extra}. Model retrained on ${r.corrections} correction${r.corrections > 1 ? "s" : ""}; ${r.recategorized} other transaction${r.recategorized === 1 ? "" : "s"} re-categorised.`);
    } catch (e) {
      onChanged(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    if (!confirm("Delete this transaction?")) return;
    await api(`/transactions/${t.id}`, { method: "DELETE" });
    onChanged("Transaction deleted.");
  }
  const low = t.category_source === "model" && t.confidence < 0.5;
  return (
    <tr>
      <td className="muted" style={{ whiteSpace: "nowrap" }}>{dateLabel(t.date)}</td>
      <td className="desc" title={t.description}>{t.description}</td>
      <td>
        <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
          <select value={t.category} disabled={busy} onChange={(e) => change(e.target.value)} style={{ padding: "4px 6px" }} aria-label="Category">
            {categories.map((c) => <option key={c}>{c}</option>)}
          </select>
          {busy && <span className="spinner" title="Retraining" />}
        </span>
      </td>
      <td>
        {t.category_source === "user" ? (
          <span className="badge">You set this</span>
        ) : (
          <span className="status" title="How sure the model is">
            <span className={`dot ${low ? "warning" : "good"}`} aria-hidden="true" />
            {low ? "Check" : ""} {pct(t.confidence * 100, 0)}
          </span>
        )}
      </td>
      <td className={`right num ${t.amount > 0 ? "delta-good" : ""}`} style={{ whiteSpace: "nowrap" }}>{t.amount > 0 ? "+" : ""}{money2(t.amount)}</td>
      <td className="right"><button className="btn small ghost" onClick={remove} aria-label="Delete">✕</button></td>
    </tr>
  );
}

function Upload({ onDone }) {
  const input = useRef();
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState("");

  async function send(file) {
    if (!file) return;
    setBusy(true);
    setErr("");
    try {
      const r = await api("/transactions/import", { method: "POST", file });
      onDone(`Imported ${r.imported} of ${r.parsed} transactions from ${file.name}` +
        (r.duplicates ? ` (${r.duplicates} already imported, skipped)` : "") +
        (r.low_confidence ? `. ${r.low_confidence} need a quick review.` : "."));
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
      input.current.value = "";
    }
  }

  return (
    <div
      className="card span-2"
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}
      style={{ borderStyle: "dashed", borderColor: drag ? "var(--accent)" : undefined, display: "flex", flexDirection: "column", justifyContent: "center", gap: 10 }}
    >
      <h2>Import a bank or UPI statement</h2>
      <p className="subtle" style={{ margin: 0 }}>
        Drop a CSV, Excel or PDF file here. Works with HDFC, SBI, ICICI, Axis and most other formats: FinSight finds the date, description and amount columns itself. Re-uploading the same statement won't create duplicates.
      </p>
      <div className="row">
        <button className="btn primary" onClick={() => input.current.click()} disabled={busy}>
          {busy && <span className="spinner" />} {busy ? "Importing…" : "Choose file"}
        </button>
        <a href="/sample_statement.csv" download>Download a sample statement</a>
      </div>
      <input ref={input} type="file" accept=".csv,.txt,.xls,.xlsx,.pdf" hidden onChange={(e) => send(e.target.files[0])} />
      {err && <div className="notice error">{err}</div>}
    </div>
  );
}

function ModelCard({ metrics, onReview }) {
  if (!metrics) return <div className="card"><Loading /></div>;
  return (
    <div className="card">
      <h2 style={{ marginBottom: 10 }}>Categorisation model</h2>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="subtle">Accuracy, known merchants</span>
        <b className="num">{pct(metrics.known_merchants.accuracy * 100)}</b>
      </div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="subtle">Accuracy, never-seen merchants</span>
        <b className="num">{pct(metrics.unseen_merchants.accuracy * 100)}</b>
      </div>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="subtle">Your corrections learned</span>
        <b className="num">{metrics.your_corrections}</b>
      </div>
      <p className="muted" style={{ fontSize: 12, margin: "8px 0" }}>TF-IDF character n-grams + logistic regression, retrained per user on every correction.</p>
      {metrics.needs_review > 0 && (
        <button className="btn small" onClick={onReview}>Review {metrics.needs_review} uncertain transaction{metrics.needs_review > 1 ? "s" : ""}</button>
      )}
    </div>
  );
}

function AddTransaction({ categories, onAdded }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ date: new Date().toISOString().slice(0, 10), description: "", amount: "", type: "debit", category: "" });
  if (!open) return <button className="btn" onClick={() => setOpen(true)}>Add manually</button>;
  return (
    <form
      className="form-grid"
      style={{ width: "100%", marginTop: 8 }}
      onSubmit={async (e) => {
        e.preventDefault();
        const amount = Math.abs(Number(f.amount)) * (f.type === "debit" ? -1 : 1);
        await api("/transactions", { method: "POST", body: { date: f.date, description: f.description, amount, category: f.category || null } });
        setOpen(false);
        setF({ ...f, description: "", amount: "" });
        onAdded();
      }}
    >
      <label className="field">Date<input type="date" required value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} /></label>
      <label className="field">Description<input required value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></label>
      <label className="field">Amount (₹)<input type="number" min="0.01" step="0.01" required value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></label>
      <label className="field">Type
        <select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="debit">Money out</option><option value="credit">Money in</option></select>
      </label>
      <label className="field">Category
        <select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
          <option value="">Let the model decide</option>
          {categories.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <div className="row"><button className="btn primary" type="submit">Add</button><button className="btn ghost" type="button" onClick={() => setOpen(false)}>Cancel</button></div>
    </form>
  );
}
