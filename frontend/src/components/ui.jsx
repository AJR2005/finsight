import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

/** Loads an API path and re-loads when `deps` change. Returns { data, error, loading, reload }. */
export function useApi(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    if (!path) return;
    setState((s) => ({ ...s, loading: true }));
    api(path)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: null, error, loading: false }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(load, [load]);
  return { ...state, reload: load };
}

export function Card({ title, subtitle, action, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-head">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatTile({ label, value, foot }) {
  return (
    <div className="card tile">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {foot && <div className="foot">{foot}</div>}
    </div>
  );
}

export function Loading({ error }) {
  if (error) return <div className="notice error">{error.message}</div>;
  return (
    <div className="empty">
      <span className="spinner" /> Loading…
    </div>
  );
}

const STATUS = {
  ok: { dot: "good", label: "On track" },
  at_risk: { dot: "warning", label: "At risk" },
  over: { dot: "critical", label: "Over budget" },
};

export function Status({ value }) {
  const s = STATUS[value] ?? STATUS.ok;
  return (
    <span className="status">
      <span className={`dot ${s.dot}`} aria-hidden="true" />
      {s.label}
    </span>
  );
}

/** Shared Recharts tooltip: rows of [color, label, formatted value]. */
export function ChartTip({ active, payload, label, title, rows }) {
  if (!active || !payload?.length) return null;
  const items = rows ? rows(payload[0].payload) : payload.map((p) => [p.color, p.name, p.value]);
  return (
    <div className="chart-tip">
      <div className="t">{title ? title(label, payload[0].payload) : label}</div>
      {items.map(([color, name, value]) => (
        <div className="r" key={name}>
          <span className="row" style={{ gap: 6 }}>
            {color && <span className="swatch" style={{ background: color }} />}
            {name}
          </span>
          <b className="num">{value}</b>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items }) {
  return (
    <div className="legend">
      {items.map(([color, label, style]) => (
        <span key={label}>
          <span className="swatch" style={{ background: color, ...style }} />
          {label}
        </span>
      ))}
    </div>
  );
}

export const axisProps = {
  tickLine: false,
  axisLine: { stroke: "var(--axis)" },
  tick: { fill: "var(--muted)", fontSize: 12 },
};
