from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Budget, Transaction, User
from ..services.categorizer import Categorizer, get_categorizer
from ..services.forecasting import to_frame


def user_corrections(db: Session, user: User) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Transaction.description, Transaction.category)
        .where(Transaction.user_id == user.id, Transaction.category_source == "user")
        .order_by(Transaction.id)
    ).all()
    return [(d, c) for d, c in rows]


def categorizer_for(db: Session, user: User) -> Categorizer:
    return get_categorizer(user.id, user_corrections(db, user))


def recategorize(db: Session, user: User) -> int:
    """Re-run the (re)trained model over every transaction the user hasn't labelled themselves."""
    model = categorizer_for(db, user)
    txns = db.scalars(select(Transaction).where(Transaction.user_id == user.id,
                                                Transaction.category_source == "model")).all()
    preds = model.predict([t.description for t in txns], [t.amount for t in txns])
    changed = 0
    for t, p in zip(txns, preds):
        if t.category != p.category:
            changed += 1
        t.category, t.confidence = p.category, p.confidence
    db.commit()
    return changed


def user_frame(db: Session, user: User):
    txns = db.scalars(select(Transaction).where(Transaction.user_id == user.id)).all()
    return to_frame(txns)


def user_budgets(db: Session, user: User) -> dict[str, float]:
    return {b.category: b.monthly_limit for b in db.scalars(select(Budget).where(Budget.user_id == user.id))}


def today() -> date:
    return date.today()
