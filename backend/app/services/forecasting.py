"""Cash-flow forecasting.

Monthly spending is forecast with Holt's damped-trend exponential smoothing (statsmodels) when there
is enough history, falling back to a weighted moving average otherwise. Every forecast reports a
backtest error (MAPE over the last few months, predicting each month from only the months before it),
so the number on screen comes with an honest measure of how good it is.
"""
from __future__ import annotations

import calendar
import warnings
from datetime import date

import numpy as np
import pandas as pd

from .merchants import NON_SPEND_CATEGORIES


def to_frame(txns) -> pd.DataFrame:
    df = pd.DataFrame([{"date": t.date, "amount": t.amount, "category": t.category,
                        "description": t.description, "id": t.id} for t in txns])
    if df.empty:
        return pd.DataFrame(columns=["date", "amount", "category", "description", "id", "month"])
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    return df


def spend_only(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["amount"] < 0) & (~df["category"].isin(NON_SPEND_CATEGORIES))]


def monthly_series(df: pd.DataFrame, today: date) -> pd.Series:
    """Total spend per *complete* month (the current month is still in progress)."""
    spend = spend_only(df)
    current = pd.Period(today, "M")
    s = (-spend.groupby("month")["amount"].sum())
    if s.empty:
        return s
    s = s.reindex(pd.period_range(s.index.min(), current - 1, freq="M"), fill_value=0.0)
    return s[s.index < current]


def _holt(values: np.ndarray) -> float:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(values, trend="add", damped_trend=True,
                                   initialization_method="estimated").fit()
    return float(max(fit.forecast(1)[0], 0))


def _wma(values: np.ndarray) -> float:
    recent = values[-6:]
    return float(np.average(recent, weights=np.arange(1, len(recent) + 1, dtype=float)))


def _median3(values: np.ndarray) -> float:
    return float(np.median(values[-3:]))


MODELS = {
    "Holt damped-trend exponential smoothing": (_holt, 6),
    "Weighted moving average (6 months)": (_wma, 1),
    "Median of last 3 months": (_median3, 1),
}


def backtest_mape(values: np.ndarray, model, horizon: int = 3) -> float | None:
    """Rolling-origin backtest: predict each of the last `horizon` months from only the months before it."""
    fn, min_len = model
    if len(values) < horizon + max(min_len, 3):
        return None
    errors = []
    for k in range(len(values) - horizon, len(values)):
        if values[k] > 0:
            errors.append(abs(fn(values[:k]) - values[k]) / values[k])
    return round(float(np.mean(errors)) * 100, 1) if errors else None


def select_model(values: np.ndarray) -> tuple[str, float, float | None]:
    """Picks whichever model had the lowest backtest error on this user's own history."""
    if len(values) == 0:
        return "No history yet", 0.0, None
    scored = []
    for name, model in MODELS.items():
        if len(values) < model[1]:
            continue
        scored.append((backtest_mape(values, model), name))
    scored.sort(key=lambda s: (s[0] is None, s[0] or 0))
    mape, name = scored[0]
    return name, MODELS[name][0](values), mape


def forecast(df: pd.DataFrame, budgets: dict[str, float], today: date, exclude_ids: set[int] | None = None) -> dict:
    """`exclude_ids` are one-off anomalies (a laptop, a holiday) left out so they don't inflate the baseline."""
    actual_df = df
    if exclude_ids:
        df = df[~df["id"].isin(exclude_ids)]
    series = monthly_series(df, today)
    values = series.to_numpy(dtype=float)
    method, next_total, mape = select_model(values)
    resid_std = float(np.std(np.diff(values))) if len(values) > 2 else next_total * 0.15

    # Per-category forecast: weighted average of the last 6 complete months.
    spend = spend_only(df)
    current = pd.Period(today, "M")
    by_cat = (-spend[spend["month"] < current].groupby(["month", "category"])["amount"].sum()).unstack(fill_value=0)
    cat_forecast = {}
    if not by_cat.empty:
        recent = by_cat.tail(6)
        w = np.arange(1, len(recent) + 1, dtype=float)
        cat_forecast = {c: round(float(np.average(recent[c], weights=w)), 2) for c in recent.columns}

    # Income forecast for projected savings.
    income = df[(df["amount"] > 0) & (df["category"].isin(["Salary", "Other Income"]))]
    inc_series = income[income["month"] < current].groupby("month")["amount"].sum().tail(6)
    next_income = float(inc_series.mean()) if not inc_series.empty else 0.0

    # Current month pace: blend actual run-rate with the forecast, weighted by how far into the month we are.
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    progress = today.day / days_in_month
    actual_spend = spend_only(actual_df)
    this_month = actual_spend[actual_spend["month"] == current]
    warnings_out = []
    for category, limit in budgets.items():
        spent = abs(float(this_month[this_month["category"] == category]["amount"].sum()))
        typical = cat_forecast.get(category, 0.0)
        run_rate = spent / progress if progress > 0 else spent
        projected = progress * run_rate + (1 - progress) * max(typical, spent)
        projected = max(projected, spent)
        status = "over" if spent > limit else "at_risk" if projected > limit else "ok"
        warnings_out.append({"category": category, "limit": limit, "spent": round(spent, 2),
                             "projected": round(projected, 2), "status": status})
    warnings_out.sort(key=lambda w: (w["status"] == "ok", -(w["projected"] / max(w["limit"], 1))))

    actual_series = monthly_series(actual_df, today)
    history = [{"month": str(m), "spend": round(float(actual_series.get(m, v)), 2), "baseline": round(float(v), 2)}
               for m, v in series.tail(12).items()]
    return {
        "history": history,
        # The model predicts the first month after the last complete one, i.e. the current month.
        "forecast_month": str(current),
        "forecast_total": round(next_total, 2),
        "forecast_low": round(max(next_total - 1.28 * resid_std, 0), 2),
        "forecast_high": round(next_total + 1.28 * resid_std, 2),
        "forecast_income": round(next_income, 2),
        "projected_savings": round(next_income - next_total, 2),
        "backtest_mape": mape,
        "method": method,
        "excluded_one_offs": len(exclude_ids or ()),
        "by_category": dict(sorted(cat_forecast.items(), key=lambda kv: -kv[1])),
        "budgets": warnings_out,
        "month_progress": round(progress, 3),
    }
