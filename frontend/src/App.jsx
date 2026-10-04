import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { api, getToken, setToken } from "./api";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Transactions from "./pages/Transactions.jsx";
import Insights from "./pages/Insights.jsx";
import Investments from "./pages/Investments.jsx";
import Goals from "./pages/Goals.jsx";

const icon = (d) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const NAV = [
  { to: "/", label: "Dashboard", icon: icon("M3 13h8V3H3zM13 21h8v-8h-8zM13 3v6h8V3zM3 21h8v-4H3z") },
  { to: "/transactions", label: "Transactions", icon: icon("M4 6h16M4 12h16M4 18h10") },
  { to: "/insights", label: "Forecast & budgets", icon: icon("M3 17l6-6 4 4 8-8M15 7h6v6") },
  { to: "/investments", label: "Investments", icon: icon("M12 2v20M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6") },
  { to: "/goals", label: "Goal planner", icon: icon("M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z") },
];

function Shell({ me, onLogout, children }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <svg width="18" height="18" viewBox="0 0 32 32"><path d="M6 23l7-8 5 5 8-11" stroke="white" strokeWidth="3.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          FinSight
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}>
              {n.icon}
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div style={{ fontWeight: 600 }}>{me?.name}</div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{me?.email}</div>
          {me?.is_demo && <ResetDemo />}
          <button className="btn small ghost" onClick={onLogout} style={{ paddingLeft: 0 }}>Log out</button>
        </div>
      </aside>
      <div>
        <nav className="mobile-nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}>{n.label}</NavLink>
          ))}
          <a href="#" onClick={(e) => { e.preventDefault(); onLogout(); }}>Log out</a>
        </nav>
        <main className="main">{children}</main>
      </div>
    </div>
  );
}

function ResetDemo() {
  const [busy, setBusy] = useState(false);
  return (
    <button
      className="btn small"
      style={{ marginBottom: 6 }}
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        await api("/demo/reset", { method: "POST" });
        window.location.reload();
      }}
    >
      {busy ? <span className="spinner" /> : null} Reset demo data
    </button>
  );
}

export default function App() {
  const [token, setTok] = useState(getToken());
  const [me, setMe] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (token) api("/me").then(setMe).catch(() => {});
  }, [token]);

  const login = (t) => {
    setToken(t);
    setTok(t);
    navigate("/");
  };
  const logout = () => {
    setToken(null);
    setTok(null);
    setMe(null);
    navigate("/login");
  };

  if (!token) {
    return (
      <Routes>
        <Route path="*" element={<Login onLogin={login} />} />
      </Routes>
    );
  }
  return (
    <Shell me={me} onLogout={logout}>
      <Routes>
        <Route path="/" element={<Dashboard me={me} onMeChange={setMe} />} />
        <Route path="/transactions" element={<Transactions />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/investments" element={<Investments />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Shell>
  );
}
