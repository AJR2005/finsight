from datetime import date
from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Transaction, User
from ..schemas import CategoryUpdate, ImportResult, TransactionIn, TransactionOut
from ..services.categorizer import evaluate_holdout
from ..services.merchants import CATEGORIES, merchant_key
from ..services.parser import ParsedTxn, StatementError, parse_statement, with_fingerprints
from .deps import categorizer_for, recategorize, user_corrections

router = APIRouter(prefix="/api", tags=["transactions"])
MAX_UPLOAD = 10 * 1024 * 1024
LOW_CONFIDENCE = 0.5


@router.get("/categories")
def categories():
    return CATEGORIES


@router.get("/transactions")
def list_transactions(
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    category: str | None = None,
    q: str | None = None,
    needs_review: bool = False,
    limit: int = Query(50, le=500),
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Transaction).where(Transaction.user_id == user.id)
    if month:
        y, m = map(int, month.split("-"))
        start = date(y, m, 1)
        end = date(y + (m == 12), m % 12 + 1, 1)
        stmt = stmt.where(Transaction.date >= start, Transaction.date < end)
    if category:
        stmt = stmt.where(Transaction.category == category)
    if q:
        stmt = stmt.where(Transaction.description.ilike(f"%{q}%"))
    if needs_review:
        stmt = stmt.where(Transaction.category_source == "model", Transaction.confidence < LOW_CONFIDENCE)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit).offset(offset)).all()
    return {"total": total, "items": [TransactionOut.model_validate(r) for r in rows]}


def _save(db: Session, user: User, parsed: list[ParsedTxn], forced_category: str | None = None) -> ImportResult:
    existing = set(db.scalars(select(Transaction.fingerprint).where(Transaction.user_id == user.id)))
    fresh = [(p, fp) for p, fp in with_fingerprints(parsed) if fp not in existing]
    preds = categorizer_for(db, user).predict([p.description for p, _ in fresh], [p.amount for p, _ in fresh])
    low = 0
    for (p, fp), pred in zip(fresh, preds):
        source = "user" if forced_category else "model"
        category = forced_category or pred.category
        low += pred.confidence < LOW_CONFIDENCE and not forced_category
        db.add(Transaction(user_id=user.id, date=p.date, description=p.description, amount=p.amount,
                           category=category, category_source=source,
                           confidence=1.0 if forced_category else pred.confidence, fingerprint=fp))
    db.commit()
    return ImportResult(parsed=len(parsed), imported=len(fresh), duplicates=len(parsed) - len(fresh), low_confidence=low)


@router.post("/transactions/import", response_model=ImportResult)
async def import_statement(file: UploadFile = File(...), user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    content = await file.read()
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 10 MB")
    try:
        parsed = parse_statement(file.filename or "statement.csv", content)
    except StatementError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(400, "Couldn't read this file. Is it a valid CSV, Excel or PDF statement?")
    return _save(db, user, parsed)


@router.post("/transactions", response_model=ImportResult)
def add_transaction(body: TransactionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.category and body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    return _save(db, user, [ParsedTxn(body.date, body.description.strip(), round(body.amount, 2))], body.category)


@router.patch("/transactions/{txn_id}/category")
def correct_category(txn_id: int, body: CategoryUpdate, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """A correction is a training label: the user's model is retrained and re-applied."""
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    txn = db.get(Transaction, txn_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    txn.category, txn.category_source, txn.confidence = body.category, "user", 1.0
    db.commit()
    similar = 0
    if body.apply_to_similar:
        key = merchant_key(txn.description)
        others = db.scalars(select(Transaction).where(Transaction.user_id == user.id,
                                                      Transaction.category_source == "model")).all()
        for o in others:
            if merchant_key(o.description) == key:
                o.category, o.confidence = body.category, 1.0
                similar += 1
        db.commit()
    changed = recategorize(db, user)
    return {"updated_similar": similar, "recategorized": changed, "corrections": len(user_corrections(db, user))}


@router.delete("/transactions/{txn_id}")
def delete_transaction(txn_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txn = db.get(Transaction, txn_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    db.delete(txn)
    db.commit()
    return {"ok": True}


@lru_cache(maxsize=1)
def _metrics():
    return evaluate_holdout()


@router.get("/model/metrics")
def model_metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    review = db.scalar(select(func.count()).where(Transaction.user_id == user.id,
                                                  Transaction.category_source == "model",
                                                  Transaction.confidence < LOW_CONFIDENCE))
    return {**_metrics(), "your_corrections": len(user_corrections(db, user)), "needs_review": review}
