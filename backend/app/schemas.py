from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    email: str


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    description: str
    amount: float
    category: str
    category_source: str
    confidence: float


class TransactionIn(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=500)
    amount: float
    category: str | None = None


class CategoryUpdate(BaseModel):
    category: str
    apply_to_similar: bool = True


class ImportResult(BaseModel):
    parsed: int
    imported: int
    duplicates: int
    low_confidence: int


class BudgetIn(BaseModel):
    category: str
    monthly_limit: float = Field(gt=0)


class BudgetOut(BudgetIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class HoldingIn(BaseModel):
    kind: str = Field(pattern="^(stock|mf)$")
    symbol: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    units: float = Field(gt=0)
    avg_cost: float = Field(gt=0)
    purchase_date: date


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: float = Field(gt=0)
    target_date: date
    current_savings: float = Field(ge=0, default=0)
    monthly_contribution: float = Field(ge=0, default=0)
    expected_return: float = Field(ge=-0.5, le=0.5, default=0.11)
    volatility: float = Field(ge=0, le=1, default=0.15)


class GoalOut(GoalIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
