"""Budgets, investments and goals."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Budget, Goal, Holding, User
from ..schemas import BudgetIn, BudgetOut, GoalIn, GoalOut, HoldingIn
from ..services.merchants import CATEGORIES
from ..services.montecarlo import plan_goal
from ..services.portfolio import portfolio_summary, refresh_price, search_mutual_funds
from .deps import today

router = APIRouter(prefix="/api", tags=["planning"])


def _owned(db: Session, model, obj_id: int, user: User):
    obj = db.get(model, obj_id)
    if not obj or obj.user_id != user.id:
        raise HTTPException(404, "Not found")
    return obj


# ---- Budgets ----
@router.get("/budgets", response_model=list[BudgetOut])
def list_budgets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Budget).where(Budget.user_id == user.id).order_by(Budget.category)).all()


@router.put("/budgets", response_model=BudgetOut)
def upsert_budget(body: BudgetIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Unknown category")
    budget = db.scalar(select(Budget).where(Budget.user_id == user.id, Budget.category == body.category))
    if budget:
        budget.monthly_limit = body.monthly_limit
    else:
        budget = Budget(user_id=user.id, **body.model_dump())
        db.add(budget)
    db.commit()
    return budget


@router.delete("/budgets/{budget_id}")
def delete_budget(budget_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, Budget, budget_id, user))
    db.commit()
    return {"ok": True}


# ---- Investments ----
@router.get("/investments")
def investments(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    holdings = db.scalars(select(Holding).where(Holding.user_id == user.id)).all()
    for h in holdings:
        refresh_price(h, db)
    db.commit()
    return portfolio_summary(holdings, today())


@router.post("/investments")
def add_holding(body: HoldingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    h = Holding(user_id=user.id, **body.model_dump())
    h.symbol = h.symbol.strip().upper() if h.kind == "stock" else h.symbol.strip()
    db.add(h)
    refresh_price(h, db)
    db.commit()
    return {"id": h.id, "live_price": h.last_price}


@router.delete("/investments/{holding_id}")
def delete_holding(holding_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, Holding, holding_id, user))
    db.commit()
    return {"ok": True}


@router.get("/investments/search-mf")
def search_mf(q: str = Query(min_length=2), user: User = Depends(get_current_user)):
    return search_mutual_funds(q)


# ---- Goals ----
@router.get("/goals", response_model=list[GoalOut])
def list_goals(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Goal).where(Goal.user_id == user.id).order_by(Goal.target_date)).all()


@router.post("/goals", response_model=GoalOut)
def create_goal(body: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = Goal(user_id=user.id, **body.model_dump())
    db.add(goal)
    db.commit()
    return goal


@router.put("/goals/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, body: GoalIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    goal = _owned(db, Goal, goal_id, user)
    for k, v in body.model_dump().items():
        setattr(goal, k, v)
    db.commit()
    return goal


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(_owned(db, Goal, goal_id, user))
    db.commit()
    return {"ok": True}


@router.post("/goals/simulate")
def simulate_goal(body: GoalIn, user: User = Depends(get_current_user)):
    """Runs the Monte Carlo for unsaved inputs, so the what-if sliders update live."""
    if body.target_date <= today():
        raise HTTPException(400, "Target date must be in the future")
    return plan_goal(body.current_savings, body.monthly_contribution, body.target_amount, body.target_date,
                     body.expected_return, body.volatility, today())
