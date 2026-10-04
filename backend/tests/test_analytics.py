from datetime import date, timedelta

import numpy as np

from app.demo import generate_transactions
from app.services.anomalies import detect_anomalies, detect_subscriptions
from app.services.categorizer import Categorizer
from app.services.forecasting import forecast
from app.services.montecarlo import plan_goal
from app.services.portfolio import xirr

TODAY = date(2026, 10, 4)


class T:  # minimal stand-in for the ORM row
    def __init__(self, i, d, desc, amt, cat):
        self.id, self.date, self.description, self.amount, self.category = i, d, desc, amt, cat


def demo_frame():
    from app.services.forecasting import to_frame

    txns = generate_transactions(TODAY)
    preds = Categorizer().predict([t.description for t in txns], [t.amount for t in txns])
    return to_frame([T(i, t.date, t.description, t.amount, p.category) for i, (t, p) in enumerate(zip(txns, preds))])


def test_categorizer_learns_from_a_correction():
    text = "UPI/123/MOHAN PANIPURI/mohan@ybl"
    assert Categorizer().predict([text], [-60])[0].category != "Food & Dining"
    model = Categorizer(corrections=[(text, "Food & Dining")])
    assert model.predict(["UPI/999/MOHAN PANIPURI/mohan@ybl/x"], [-80])[0].category == "Food & Dining"


def test_categorizer_common_merchants():
    preds = Categorizer().predict(
        ["UPI-SWIGGY-swiggy@icici-624512378901-UPI", "POS 4160XXXX DMART POWAI", "NEFT CR-XYZ-SALARY SEP"],
        [-486, -1842, 92000])
    assert [p.category for p in preds] == ["Food & Dining", "Groceries", "Salary"]


def test_detects_planted_anomalies_and_subscriptions():
    df = demo_frame()
    anomalies = {a["description"] for a in detect_anomalies(df, today=TODAY)}
    assert any("CROMA" in a for a in anomalies)
    assert any("Party order" in a for a in anomalies)
    subs = {s["merchant"] for s in detect_subscriptions(df, today=TODAY) if s["active"]}
    assert {"netflix", "spotify", "cultfit"} <= subs


def test_forecast_excludes_one_offs():
    df = demo_frame()
    one_offs = {a["id"] for a in detect_anomalies(df, lookback_days=36500, today=TODAY)}
    with_spikes = forecast(df, {}, TODAY)["forecast_total"]
    clean = forecast(df, {}, TODAY, exclude_ids=one_offs)
    assert clean["forecast_total"] <= with_spikes
    assert clean["backtest_mape"] is not None and clean["backtest_mape"] < 40


def test_xirr_matches_simple_compounding():
    # ₹1,00,000 growing to ₹1,10,000 in exactly one year = 10%.
    r = xirr([(date(2025, 1, 1), -100000), (date(2026, 1, 1), 110000)])
    assert abs(r - 0.10) < 1e-4
    assert xirr([(date(2025, 1, 1), -100)]) is None


def test_monte_carlo_sanity():
    certain = plan_goal(0, 10000, 100000, TODAY + timedelta(days=365 * 2), 0.0, 0.0, TODAY, n_paths=500)
    assert certain["probability"] == 100.0
    impossible = plan_goal(0, 1000, 10_000_000, TODAY + timedelta(days=365), 0.08, 0.15, TODAY, n_paths=500)
    assert impossible["probability"] == 0.0
    assert impossible["required_monthly_80"] > 500000
    fan = certain["fan"]
    assert np.all(np.diff([p["p50"] for p in fan]) >= 0)
