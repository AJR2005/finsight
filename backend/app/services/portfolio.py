"""Live prices, net worth and XIRR."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx

from ..config import LIVE_PRICES

log = logging.getLogger(__name__)
PRICE_TTL = timedelta(minutes=15)


def fetch_price(kind: str, symbol: str) -> float | None:
    """Stocks from Yahoo Finance (e.g. INFY.NS), mutual fund NAVs from mfapi.in (AMFI scheme code)."""
    if not LIVE_PRICES:
        return None
    try:
        if kind == "stock":
            r = httpx.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                          params={"range": "1d", "interval": "1d"},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=6)
            r.raise_for_status()
            return float(r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"])
        r = httpx.get(f"https://api.mfapi.in/mf/{symbol}/latest", timeout=6)
        r.raise_for_status()
        return float(r.json()["data"][0]["nav"])
    except Exception as exc:  # network errors, bad symbol, API format change
        log.warning("Price lookup failed for %s %s: %s", kind, symbol, exc)
        return None


def search_mutual_funds(query: str) -> list[dict]:
    if not LIVE_PRICES:
        return []
    try:
        r = httpx.get("https://api.mfapi.in/mf/search", params={"q": query}, timeout=6)
        r.raise_for_status()
        return [{"code": str(f["schemeCode"]), "name": f["schemeName"]} for f in r.json()[:15]]
    except Exception as exc:
        log.warning("MF search failed: %s", exc)
        return []


def refresh_price(holding, db) -> None:
    fresh = holding.last_price_at and datetime.utcnow() - holding.last_price_at < PRICE_TTL
    if fresh:
        return
    price = fetch_price(holding.kind, holding.symbol)
    if price:
        holding.last_price = price
        holding.last_price_at = datetime.utcnow()
        db.add(holding)


def xirr(cashflows: list[tuple[date, float]]) -> float | None:
    """Annualised return for irregular cash flows (negative = invested, positive = value today).

    Solves sum(cf / (1 + r) ** years) = 0 with Newton's method, falling back to bisection.
    """
    if len(cashflows) < 2 or not any(c < 0 for _, c in cashflows) or not any(c > 0 for _, c in cashflows):
        return None
    t0 = min(d for d, _ in cashflows)
    years = [((d - t0).days / 365.0, c) for d, c in cashflows]
    if max(y for y, _ in years) < 1 / 365:
        return None

    def npv(r):
        return sum(c / (1 + r) ** y for y, c in years)

    def d_npv(r):
        return sum(-y * c / (1 + r) ** (y + 1) for y, c in years)

    r = 0.1
    for _ in range(100):
        f, df = npv(r), d_npv(r)
        if df == 0:
            break
        step = f / df
        r -= step
        if r <= -0.9999:
            break
        if abs(step) < 1e-9:
            return r
    lo, hi = -0.9999, 100.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def portfolio_summary(holdings, today: date | None = None) -> dict:
    today = today or date.today()
    rows, flows = [], []
    invested_total = value_total = 0.0
    for h in holdings:
        price = h.last_price or h.avg_cost
        invested = h.units * h.avg_cost
        value = h.units * price
        invested_total += invested
        value_total += value
        flows.append((h.purchase_date, -invested))
        own_xirr = xirr([(h.purchase_date, -invested), (today, value)])
        rows.append({
            "id": h.id, "kind": h.kind, "symbol": h.symbol, "name": h.name, "units": h.units,
            "avg_cost": h.avg_cost, "price": round(price, 2), "invested": round(invested, 2),
            "value": round(value, 2), "gain": round(value - invested, 2),
            "gain_pct": round((value / invested - 1) * 100, 2) if invested else 0.0,
            "xirr": round(own_xirr * 100, 2) if own_xirr is not None else None,
            "live": h.last_price_at is not None,
            "price_at": h.last_price_at.isoformat() if h.last_price_at else None,
            "purchase_date": h.purchase_date.isoformat(),
        })
    total_xirr = xirr(flows + [(today, value_total)]) if holdings else None
    allocation: dict[str, float] = {}
    for r in rows:
        label = "Mutual funds" if r["kind"] == "mf" else "Stocks"
        allocation[label] = allocation.get(label, 0) + r["value"]
    return {
        "holdings": sorted(rows, key=lambda r: -r["value"]),
        "invested": round(invested_total, 2),
        "value": round(value_total, 2),
        "gain": round(value_total - invested_total, 2),
        "gain_pct": round((value_total / invested_total - 1) * 100, 2) if invested_total else 0.0,
        "xirr": round(total_xirr * 100, 2) if total_xirr is not None else None,
        "allocation": [{"name": k, "value": round(v, 2)} for k, v in allocation.items()],
    }
