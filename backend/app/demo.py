"""Seeds a demo account with 12 months of realistic transactions, so recruiters can try the app instantly.

Transactions are run through the real classifier (not pre-labelled), so the demo shows what the model
actually does, including a few local merchants it isn't sure about.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth import hash_password
from .config import DEMO_EMAIL, DEMO_PASSWORD
from .models import Budget, Goal, Holding, SubscriptionFlag, Transaction, User
from .services.categorizer import get_categorizer
from .services.parser import ParsedTxn, with_fingerprints
from .services.training_data import narration

# (merchant, category, min, max, average count per month)
VARIABLE = [
    (["ZOMATO", "SWIGGY"], "Food & Dining", 220, 720, 11),
    (["STARBUCKS", "CHAAYOS", "THIRD WAVE COFFEE", "CAFE COFFEE DAY"], "Food & Dining", 150, 480, 5),
    (["BLINKIT", "ZEPTO", "BIGBASKET", "DMART"], "Groceries", 350, 2400, 6),
    (["UBER", "OLA CABS", "RAPIDO"], "Transport", 70, 460, 9),
    (["MUMBAI METRO"], "Transport", 40, 120, 4),
    (["INDIAN OIL", "HP PETROL PUMP", "BHARAT PETROLEUM"], "Fuel", 1200, 2400, 2),
    (["AMAZON", "FLIPKART", "MYNTRA", "DECATHLON", "NYKAA"], "Shopping", 450, 3800, 3),
    (["BOOKMYSHOW", "PVR CINEMAS", "DISTRICT"], "Entertainment", 280, 1300, 2),
    (["APOLLO PHARMACY", "PHARMEASY", "1MG"], "Health", 180, 1400, 1),
    (["UDEMY", "KINDLE BOOKS"], "Education", 399, 899, 0.4),
]
# Local merchants and people the model has never seen: these land in "Needs review".
UNKNOWN = ["UPI/{r}/RAMESH TEA STALL/ramesh.t@okaxis/Pay", "UPI/{r}/AMIT VERMA/amitv@ybl/Sent",
           "UPI/{r}/LAXMI XEROX/laxmixerox@okhdfcbank", "UPI/{r}/MOHAN PANIPURI/mohan@ybl",
           "UPI/{r}/SNEHA KULKARNI/sneha.k@oksbi/Dinner split"]
FIXED = [  # (day, merchant, category, amount)
    (3, "NOBROKER RENT", "Rent", 22000),
    (5, "SIP HDFC MF", "Investments", 10000),
    (7, "NETFLIX", "Subscriptions", 649),
    (10, "COIN BY ZERODHA", "Investments", 5000),
    (12, "SPOTIFY", "Subscriptions", 119),
    (15, "CULTFIT", "Subscriptions", 1499),
    (18, "AIRTEL", "Bills & Utilities", 599),
    (20, "GOOGLE ONE", "Subscriptions", 130),
]


def _month_starts(today: date, months: int) -> list[date]:
    out, y, m = [], today.year, today.month
    for _ in range(months):
        out.append(date(y, m, 1))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return sorted(out)


def generate_transactions(today: date, months: int = 12, seed: int = 2028) -> list[ParsedTxn]:
    rng = random.Random(seed)
    txns: list[ParsedTxn] = []

    def add(d: date, text: str, amount: float):
        if d <= today:
            txns.append(ParsedTxn(d, text, round(amount, 2)))

    for i, start in enumerate(_month_starts(today, months)):
        ndays = ((start.replace(day=28) + timedelta(days=4)).replace(day=1) - start).days
        mon = start.strftime("%b").upper()
        # Salary with a raise 5 months ago.
        salary = 85000 if i < months - 5 else 92000
        add(start, f"NEFT CR-ACME0001234-ACME TECHNOLOGIES PVT LTD-SALARY {mon}", salary)
        for day, merchant, category, amount in FIXED:
            add(start + timedelta(days=day - 1), narration(merchant, category, rng), -amount)
        # Electricity: higher in summer (Apr-Jun) because of AC.
        power = rng.uniform(2100, 2700) if start.month in (4, 5, 6) else rng.uniform(1100, 1700)
        add(start + timedelta(days=21), narration("ADANI ELECTRICITY", "Bills & Utilities", rng), -power)
        add(start + timedelta(days=rng.randint(5, 25)), narration("ATM WDL", "Cash Withdrawal", rng),
            -rng.choice([2000, 3000, 5000]))
        # Food spending creeps up over the year, which the forecast should pick up.
        growth = 1 + 0.025 * i
        for merchants, category, lo, hi, per_month in VARIABLE:
            count = max(0, round(rng.gauss(per_month * (growth if category == "Food & Dining" else 1), 1)))
            for _ in range(count):
                d = start + timedelta(days=rng.randrange(ndays))
                add(d, narration(rng.choice(merchants), category, rng), -rng.uniform(lo, hi) * growth ** 0.5)
        for _ in range(rng.randint(2, 4)):
            d = start + timedelta(days=rng.randrange(ndays))
            add(d, rng.choice(UNKNOWN).format(r=rng.randint(10**11, 10**12 - 1)), -rng.uniform(30, 900))
        if i % 3 == 2:
            add(start + timedelta(days=27), "INTEREST CREDIT FOR QUARTER", rng.uniform(900, 1400))
        if rng.random() < 0.5:
            add(start + timedelta(days=rng.randrange(ndays)), narration("CASHBACK", "Other Income", rng),
                rng.uniform(50, 300))
        if i == months - 3:
            add(start + timedelta(days=14), narration("MAKEMYTRIP", "Travel", rng), -18400)
            add(start + timedelta(days=15), narration("INDIGO", "Travel", rng), -9600)

    # Anomalies to find: a laptop last month and a big party order recently.
    add(today - timedelta(days=32), "POS XXXX4521 CROMA LOWER PAREL MUMBAI", -54999)
    add(today - timedelta(days=9), "UPI/482910384712/ZOMATO/zomato@hdfcbank/Party order", -4850)
    return txns


def seed_demo(db: Session, reset: bool = False, today: date | None = None) -> User:
    today = today or date.today()
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user and not reset:
        latest = db.scalar(select(Transaction.date).where(Transaction.user_id == user.id)
                           .order_by(Transaction.date.desc()).limit(1))
        if latest and (today - latest).days < 7:
            return user  # still fresh
    if user:
        for model in (Transaction, Budget, Holding, Goal, SubscriptionFlag):
            db.execute(delete(model).where(model.user_id == user.id))
    else:
        user = User(email=DEMO_EMAIL, name="Demo User", password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
    user.cash_balance = 142500
    db.flush()

    txns = generate_transactions(today)
    preds = get_categorizer(user.id, []).predict([t.description for t in txns], [t.amount for t in txns])
    for (t, fp), p in zip(with_fingerprints(txns), preds):
        db.add(Transaction(user_id=user.id, date=t.date, description=t.description, amount=t.amount,
                           category=p.category, category_source="model", confidence=p.confidence, fingerprint=fp))

    for category, limit in [("Food & Dining", 7500), ("Groceries", 9000), ("Shopping", 7000),
                            ("Transport", 3000), ("Entertainment", 2500), ("Subscriptions", 2500)]:
        db.add(Budget(user_id=user.id, category=category, monthly_limit=limit))

    def ago(days):
        return today - timedelta(days=days)

    # Prices are fallbacks for when live quotes are unreachable; live prices replace them when online.
    for kind, symbol, name, units, cost, bought, fallback in [
        ("stock", "INFY.NS", "Infosys", 15, 1450, ago(540), 1520),
        ("stock", "TCS.NS", "Tata Consultancy Services", 5, 3400, ago(420), 3480),
        ("stock", "HDFCBANK.NS", "HDFC Bank", 12, 1550, ago(300), 1720),
        ("stock", "RELIANCE.NS", "Reliance Industries", 10, 2450, ago(200), 2580),
        ("mf", "122639", "Parag Parikh Flexi Cap Fund - Direct Growth", 420.5, 62.4, ago(600), 86.1),
        ("mf", "120716", "UTI Nifty 50 Index Fund - Direct Growth", 310.2, 138.5, ago(380), 162.3),
    ]:
        db.add(Holding(user_id=user.id, kind=kind, symbol=symbol, name=name, units=units, avg_cost=cost,
                       purchase_date=bought, last_price=fallback, last_price_at=None))

    for name, target, years, current, monthly, ret, vol in [
        ("Emergency fund (6 months)", 300000, 1.5, 142500, 8000, 0.065, 0.02),
        ("Masters abroad", 2000000, 3.5, 300000, 30000, 0.11, 0.15),
        ("First car", 800000, 5, 0, 9000, 0.10, 0.13),
    ]:
        target_date = today + timedelta(days=round(years * 365))
        db.add(Goal(user_id=user.id, name=name, target_amount=target, target_date=target_date,
                    current_savings=current, monthly_contribution=monthly, expected_return=ret, volatility=vol))
    db.commit()
    return user


if __name__ == "__main__":
    from .database import Base, SessionLocal, engine

    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        u = seed_demo(session, reset=True)
        print(f"Seeded {DEMO_EMAIL} / {DEMO_PASSWORD} at {datetime.now():%H:%M}")
