from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import TransactionType


class OperationCreate(BaseModel):
    telegram_id: int
    text: str
    default_type: TransactionType = TransactionType.expense


class BudgetCreate(BaseModel):
    telegram_id: int
    category: str
    amount: Decimal = Field(gt=0)


class GoalCreate(BaseModel):
    telegram_id: int
    title: str
    target_amount: Decimal = Field(gt=0)
    due_date: date | None = None


class TransactionOut(BaseModel):
    id: UUID
    amount: Decimal
    type: TransactionType
    comment: str | None
    is_personal: bool
    category: str
    tag: str | None


class MiniAppBootstrap(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    invite_code: str | None = None


class ManualTransactionCreate(BaseModel):
    telegram_id: int
    amount: Decimal = Field(gt=0)
    type: TransactionType
    category: str
    date: datetime
    comment: str | None = None
    tag: str | None = None
    is_personal: bool = False


class TransactionCategoryUpdate(BaseModel):
    category: str


class BudgetPlanItem(BaseModel):
    category: str
    amount: Decimal = Field(ge=0)


class BudgetPlanCreate(BaseModel):
    telegram_id: int
    month: datetime
    items: list[BudgetPlanItem]
