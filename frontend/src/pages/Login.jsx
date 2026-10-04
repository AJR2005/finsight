import { useState } from "react";
import { api } from "../api";

export default function Login({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e, demo = false) {
    e?.preventDefault();
    setError("");
    setBusy(true);
    try {
      const res =
        mode === "register" && !demo
          ? await api("/auth/register", { method: "POST", body: form })
          : await api("/auth/login", {
              method: "POST",
              form: demo
                ? { username: "demo@finsight.app", password: "demo1234" }
                : { username: form.email, password: form.password },
            });
      onLogin(res.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <div className="card">
        <div className="brand" style={{ padding: 0 }}>
          <span className="brand-mark">
            <svg width="18" height="18" viewBox="0 0 32 32"><path d="M6 23l7-8 5 5 8-11" stroke="white" strokeWidth="3.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          FinSight
        </div>
        <p className="subtle" style={{ margin: "10px 0 0" }}>
          Upload your bank statements. FinSight categorises every transaction, forecasts your spending and tells you if your goals are on track.
        </p>
        <button className="btn primary" style={{ width: "100%", justifyContent: "center", marginTop: 18 }} onClick={(e) => submit(e, true)} disabled={busy}>
          Try the demo account
        </button>
        <div className="divider" style={{ marginTop: 16 }}>or {mode === "login" ? "log in" : "create an account"}</div>
        <form onSubmit={submit}>
          {mode === "register" && (
            <label className="field">Name<input required value={form.name} onChange={set("name")} /></label>
          )}
          <label className="field">Email<input type="email" required value={form.email} onChange={set("email")} autoComplete="email" /></label>
          <label className="field">Password<input type="password" required minLength={6} value={form.password} onChange={set("password")} autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
          {error && <div className="notice error">{error}</div>}
          <button className="btn" type="submit" disabled={busy} style={{ justifyContent: "center" }}>
            {busy && <span className="spinner" />} {mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
        <p className="subtle" style={{ fontSize: 13, textAlign: "center", marginBottom: 0 }}>
          {mode === "login" ? "New here? " : "Have an account? "}
          <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Create an account" : "Log in"}
          </a>
        </p>
      </div>
    </div>
  );
}
