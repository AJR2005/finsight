from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_token, get_current_user, hash_password, verify_password
from ..config import DEMO_EMAIL
from ..database import get_db
from ..models import User
from ..schemas import RegisterIn, TokenOut

router = APIRouter(prefix="/api", tags=["auth"])


def _token(user: User) -> TokenOut:
    return TokenOut(access_token=create_token(user.id), name=user.name, email=user.email)


@router.post("/auth/register", response_model=TokenOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return _token(user)


@router.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return _token(user)


class MeOut(BaseModel):
    name: str
    email: str
    cash_balance: float
    is_demo: bool


class MeIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    cash_balance: float | None = None


def _me(user: User) -> MeOut:
    return MeOut(name=user.name, email=user.email, cash_balance=user.cash_balance or 0,
                 is_demo=user.email == DEMO_EMAIL)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return _me(user)


@router.patch("/me", response_model=MeOut)
def update_me(body: MeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip()
    if body.cash_balance is not None:
        user.cash_balance = body.cash_balance
    db.commit()
    return _me(user)


@router.post("/demo/reset")
def reset_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..demo import seed_demo

    if user.email != DEMO_EMAIL:
        raise HTTPException(403, "Only the demo account can be reset")
    seed_demo(db, reset=True)
    return {"ok": True}
