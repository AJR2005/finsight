"""Unusual-charge and recurring-payment detection."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from .forecasting import spend_only
from .merchants import merchant_key

Z_THRESHOLD = 3.5  # modified z-score cut-off (Iglewicz & Hoaglin)
MIN_HISTORY = 5
# Fixed, planned payments are never "unusual" even when they dwarf the category median.
SKIP_CATEGORIES = {"Rent", "EMI & Loans", "Subscriptions", "Bills & Utilities"}


def detect_anomalies(df: pd.DataFrame, lookback_days: int = 90, today: date | None = None) -> list[dict]:
    """Flags debits far above what is normal for their category.

    Uses the median and MAD instead of mean and standard deviation, so one big purchase can't hide
    another by inflating the spread. Each flag says how many times larger than usual it is.
    """
    spend = spend_only(df).copy()
    if spend.empty:
        return []
    recurring = {s["merchant"] for s in detect_subscriptions(df, today)}
    spend["merchant"] = spend["description"].map(merchant_key)
    spend = spend[~spend["category"].isin(SKIP_CATEGORIES) & ~spend["merchant"].isin(recurring)]
    spend["abs"] = -spend["amount"]
    today = today or date.today()
    cutoff = pd.Timestamp(today - timedelta(days=lookback_days))
    out = []
    for category, group in spend.groupby("category"):
        if len(group) < MIN_HISTORY:
            continue
        values = group["abs"].to_numpy()
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median))) or median * 0.1 or 1.0
        z = 0.6745 * (values - median) / mad
        for (_, row), score in zip(group.iterrows(), z):
            if score > Z_THRESHOLD and row["date"] >= cutoff and row["abs"] > median * 2:
                out.append({
                    "id": int(row["id"]), "date": row["date"].date().isoformat(),
                    "description": row["description"], "category": category,
                    "amount": round(float(row["abs"]), 2), "typical": round(median, 2),
                    "times_typical": round(float(row["abs"]) / median, 1), "score": round(float(score), 1),
                })
    return sorted(out, key=lambda a: a["date"], reverse=True)


def detect_subscriptions(df: pd.DataFrame, today: date | None = None) -> list[dict]:
    """Finds payments to the same merchant at a regular interval for a similar amount."""
    debits = df[df["amount"] < 0].copy()
    if debits.empty:
        return []
    today = today or date.today()
    debits["merchant"] = debits["description"].map(merchant_key)
    debits["abs"] = -debits["amount"]
    out = []
    for merchant, group in debits.groupby("merchant"):
        if len(group) < 3 or merchant == "unknown":
            continue
        group = group.sort_values("date")
        gaps = group["date"].diff().dt.days.dropna().to_numpy()
        median_gap = float(np.median(gaps))
        if 26 <= median_gap <= 35:
            period = "monthly"
        elif 6 <= median_gap <= 8:
            period = "weekly"
        elif 85 <= median_gap <= 95:
            period = "quarterly"
        elif 355 <= median_gap <= 375:
            period = "yearly"
        else:
            continue
        # Regular timing: most gaps within 20% of the median.
        if np.mean(np.abs(gaps - median_gap) <= max(3, 0.2 * median_gap)) < 0.7:
            continue
        amounts = group["abs"].to_numpy()
        # Similar amount each time (utility bills are allowed to vary more).
        is_bill = (group["category"] == "Bills & Utilities").any()
        if np.std(amounts) / np.mean(amounts) > (0.35 if is_bill else 0.15):
            continue
        last = group["date"].iloc[-1].date()
        next_due = last + timedelta(days=round(median_gap))
        monthly_cost = float(amounts[-1]) * 30.4 / median_gap
        out.append({
            "merchant": merchant,
            "description": group["description"].iloc[-1],
            "category": group["category"].mode().iloc[0],
            "period": period,
            "amount": round(float(amounts[-1]), 2),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(monthly_cost * 12, 2),
            "occurrences": int(len(group)),
            "first_seen": group["date"].iloc[0].date().isoformat(),
            "last_charged": last.isoformat(),
            "next_due": next_due.isoformat(),
            # Still being charged if the last payment is within ~1.5 periods.
            "active": (today - last).days <= median_gap * 1.5,
            "price_change": round(float(amounts[-1] - amounts[-2]), 2) if len(amounts) > 1 else 0.0,
        })
    return sorted(out, key=lambda s: (-s["active"], -s["monthly_cost"]))
