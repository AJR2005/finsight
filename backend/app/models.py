from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Bank balance the user enters; added to investments for net worth.
    cash_balance: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"
    # The fingerprint stops the same statement row being imported twice.
    __table_args__ = (UniqueConstraint("user_id", "fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(500))
    # Positive = money in (credit), negative = money out (debit).
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(50), default="Other")
    # "model" = predicted by the classifier, "user" = corrected by the user.
    category_source: Mapped[str] = mapped_column(String(10), default="model")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    fingerprint: Mapped[str] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    monthly_limit: Mapped[float] = mapped_column(Float)


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # "stock" uses a Yahoo symbol (e.g. INFY.NS); "mf" uses an AMFI scheme code (e.g. 119551).
    kind: Mapped[str] = mapped_column(String(10))
    symbol: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    units: Mapped[float] = mapped_column(Float)
    avg_cost: Mapped[float] = mapped_column(Float)
    purchase_date: Mapped[date] = mapped_column(Date)
    # Last known price, used when live prices are unavailable.
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_price_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[float] = mapped_column(Float)
    target_date: Mapped[date] = mapped_column(Date)
    current_savings: Mapped[float] = mapped_column(Float, default=0)
    monthly_contribution: Mapped[float] = mapped_column(Float, default=0)
    expected_return: Mapped[float] = mapped_column(Float, default=0.11)  # annual
    volatility: Mapped[float] = mapped_column(Float, default=0.15)  # annual


class SubscriptionFlag(Base):
    """Remembers which detected recurring payments the user has reviewed."""

    __tablename__ = "subscription_flags"
    __table_args__ = (UniqueConstraint("user_id", "merchant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    merchant: Mapped[str] = mapped_column(String(120))
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=True)
