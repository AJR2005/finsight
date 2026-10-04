from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Holding, SubscriptionFlag, User
from ..services.anomalies import detect_anomalies, detect_subscriptions
from ..services.forecasting import forecast, spend_only
from ..services.merchants import INCOME_CATEGORIES, merchant_key
from ..services.portfolio import portfolio_summary
from .deps import today, user_budgets, user_frame

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/insights/forecast")
def get_forecast(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    df = user_frame(db, user)
    one_offs = {a["id"] for a in detect_anomalies(df, lookback_days=36500, today=today())}
    return forecast(df, user_budgets(db, user), today(), exclude_ids=one_offs)


@router.get("/insights/anomalies")
def get_anomalies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return detect_anomalies(user_frame(db, user), today=today())


@router.get("/insights/subscriptions")
def get_subscriptions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reviewed = set(db.scalars(select(SubscriptionFlag.merchant).where(SubscriptionFlag.user_id == user.id)))
    subs = detect_subscriptions(user_frame(db, user), today=today())
    for s in subs:
        s["reviewed"] = s["merchant"] in reviewed
    active = [s for s in subs if s["active"]]
    return {
        "items": subs,
        "monthly_total": round(sum(s["monthly_cost"] for s in active), 2),
        "annual_total": round(sum(s["annual_cost"] for s in active), 2),
        "unreviewed": sum(1 for s in active if not s["reviewed"]),
    }


@router.post("/insights/subscriptions/{merchant}/review")
def review_subscription(merchant: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.scalar(select(SubscriptionFlag).where(SubscriptionFlag.user_id == user.id,
                                                    SubscriptionFlag.merchant == merchant)):
        db.add(SubscriptionFlag(user_id=user.id, merchant=merchant))
        db.commit()
    return {"ok": True}


@router.get("/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import pandas as pd

    df = user_frame(db, user)
    now = today()
    current = pd.Period(now, "M")
    holdings = db.scalars(select(Holding).where(Holding.user_id == user.id)).all()
    portfolio = portfolio_summary(holdings, now)
    base = {"net_worth": round((user.cash_balance or 0) + portfolio["value"], 2),
            "cash_balance": user.cash_balance or 0, "investments": portfolio["value"]}
    if df.empty:
        return {**base, "empty": True, "monthly": [], "categories": [], "top_merchants": [], "recent": []}

    spend = spend_only(df)
    income = df[(df["amount"] > 0) & df["category"].isin(INCOME_CATEGORIES)]
    months = pd.period_range(current - 11, current, freq="M")
    sp = (-spend.groupby("month")["amount"].sum()).reindex(months, fill_value=0)
    inc = income.groupby("month")["amount"].sum().reindex(months, fill_value=0)
    monthly = [{"month": str(m), "spend": round(float(sp[m]), 2), "income": round(float(inc[m]), 2),
                "savings": round(float(inc[m] - sp[m]), 2)} for m in months]

    this_month = spend[spend["month"] == current]
    last_month = spend[spend["month"] == current - 1]
    cats = (-this_month.groupby("category")["amount"].sum()).sort_values(ascending=False)
    last_cats = -last_month.groupby("category")["amount"].sum()
    categories = [{"category": c, "amount": round(float(v), 2),
                   "last_month": round(float(last_cats.get(c, 0)), 2)} for c, v in cats.items()]

    recent90 = spend[spend["date"] >= pd.Timestamp(now) - pd.Timedelta(days=90)].copy()
    recent90["merchant"] = recent90["description"].map(merchant_key)
    grouped = recent90.groupby("merchant")["amount"].agg(["sum", "count"])
    grouped["spent"] = -grouped["sum"]
    top = grouped.sort_values("spent", ascending=False).head(8)
    top_merchants = [{"merchant": m.title(), "amount": round(float(r["spent"]), 2), "count": int(r["count"])}
                     for m, r in top.iterrows()]

    total_inc = sum(m["income"] for m in monthly)
    savings_rate = (total_inc - sum(m["spend"] for m in monthly)) / total_inc * 100 if total_inc else 0
    recent = df.sort_values(["date", "id"], ascending=False).head(8)
    return {
        **base,
        "empty": False,
        "month": str(current),
        "month_spend": monthly[-1]["spend"],
        "month_income": monthly[-1]["income"],
        "last_month_spend": monthly[-2]["spend"],
        "savings_rate_12m": round(savings_rate, 1),
        "monthly": monthly,
        "categories": categories,
        "top_merchants": top_merchants,
        "recent": [{"id": int(r["id"]), "date": r["date"].date().isoformat(), "description": r["description"],
                    "amount": float(r["amount"]), "category": r["category"]} for _, r in recent.iterrows()],
    }
