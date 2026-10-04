"""Monte Carlo goal planner.

Simulates thousands of possible market paths month by month (log-normal returns, i.e. geometric
Brownian motion) with a fixed monthly contribution, and reports the probability of hitting the target.
"""
from __future__ import annotations

from datetime import date

import numpy as np


def months_between(start: date, end: date) -> int:
    return max((end.year - start.year) * 12 + (end.month - start.month), 1)


def simulate(current: float, monthly: float, months: int, annual_return: float, annual_vol: float,
             n_paths: int = 10_000, seed: int | None = 42) -> np.ndarray:
    """Returns an (n_paths, months + 1) array of portfolio values."""
    rng = np.random.default_rng(seed)
    mu = np.log1p(annual_return) / 12  # monthly log drift giving the expected annual return
    sigma = annual_vol / np.sqrt(12)
    shocks = rng.normal(mu - 0.5 * sigma**2, sigma, size=(n_paths, months))
    growth = np.exp(shocks)
    values = np.empty((n_paths, months + 1))
    values[:, 0] = current
    for m in range(months):
        values[:, m + 1] = values[:, m] * growth[:, m] + monthly
    return values


def required_monthly(current: float, target: float, months: int, annual_return: float, annual_vol: float,
                     confidence: float = 0.8) -> float:
    """Smallest monthly contribution that reaches the target with the given probability (bisection)."""
    lo, hi = 0.0, max(target / months * 2, 1000.0)
    while _probability(current, hi, months, annual_return, annual_vol, target) < confidence:
        hi *= 2
        if hi > target * 10:
            break
    for _ in range(30):
        mid = (lo + hi) / 2
        if _probability(current, mid, months, annual_return, annual_vol, target) >= confidence:
            hi = mid
        else:
            lo = mid
    return round(hi / 100) * 100  # round to nearest ₹100


def _probability(current, monthly, months, r, vol, target, n_paths=4000) -> float:
    final = simulate(current, monthly, months, r, vol, n_paths=n_paths, seed=7)[:, -1]
    return float(np.mean(final >= target))


def plan_goal(current: float, monthly: float, target: float, target_date: date, annual_return: float,
              annual_vol: float, today: date | None = None, n_paths: int = 10_000) -> dict:
    today = today or date.today()
    months = months_between(today, target_date)
    values = simulate(current, monthly, months, annual_return, annual_vol, n_paths=n_paths)
    final = values[:, -1]
    p10, p50, p90 = np.percentile(values, [10, 50, 90], axis=0)
    # Thin the fan chart to at most ~60 points.
    step = max(1, months // 60)
    idx = list(range(0, months + 1, step))
    if idx[-1] != months:
        idx.append(months)
    fan = [{"month": i, "p10": round(float(p10[i])), "p50": round(float(p50[i])), "p90": round(float(p90[i])),
            "contributed": round(current + monthly * i)} for i in idx]
    return {
        "months": months,
        "probability": round(float(np.mean(final >= target)) * 100, 1),
        "median_final": round(float(np.median(final))),
        "p10_final": round(float(np.percentile(final, 10))),
        "p90_final": round(float(np.percentile(final, 90))),
        "total_contributed": round(current + monthly * months),
        "required_monthly_80": required_monthly(current, target, months, annual_return, annual_vol, 0.8),
        "paths": n_paths,
        "fan": fan,
    }
