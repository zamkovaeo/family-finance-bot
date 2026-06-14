from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import Category, Transaction, User
from app.models.enums import CategoryKind, TransactionType
from app.schemas.finance import (
    BudgetCreate,
    BudgetPlanCreate,
    GoalCreate,
    ManualTransactionCreate,
    MiniAppBootstrap,
    OperationCreate,
)
from app.services.defaults import EXPENSE_CATEGORIES, INCOME_CATEGORIES
from app.services.family_service import ensure_user
from app.services.analytics_service import AnalyticsService
from app.services.finance_service import FinanceService
from app.services.reporting_service import ReportingService
from app.utils.formatting import money

router = APIRouter()
finance = FinanceService()
analytics = AnalyticsService()
reports = ReportingService()


async def user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if not user:
        raise HTTPException(status_code=404, detail="User is not registered in Telegram bot")
    return user


@router.post("/miniapp/bootstrap")
async def miniapp_bootstrap(payload: MiniAppBootstrap, session: AsyncSession = Depends(get_session)) -> dict:
    user = await ensure_user(
        session,
        telegram_id=payload.telegram_id,
        username=payload.username,
        first_name=payload.first_name,
        invite_code=payload.invite_code,
    )
    return {"telegram_id": user.telegram_id, "family_id": str(user.family_id), "role": user.role.value}


@router.get("/miniapp/categories/{telegram_id}")
async def miniapp_categories(telegram_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    existing = list((await session.scalars(select(Category).where(Category.family_id == user.family_id))).all())
    by_kind = {
        CategoryKind.expense: [{"name": name, "emoji": emoji} for name, emoji, _ in EXPENSE_CATEGORIES],
        CategoryKind.income: [{"name": name, "emoji": emoji} for name, emoji, _ in INCOME_CATEGORIES],
    }
    for category in existing:
        if not any(item["name"].lower() == category.name.lower() for item in by_kind[category.kind]):
            by_kind[category.kind].append({"name": category.name, "emoji": category.emoji})
    return {"expense": by_kind[CategoryKind.expense], "income": by_kind[CategoryKind.income]}


@router.get("/miniapp/family-members/{telegram_id}")
async def miniapp_family_members(telegram_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    members = list(
        (
            await session.scalars(
                select(User)
                .where(User.family_id == user.family_id)
                .order_by(User.created_at.asc())
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": str(member.id),
                "telegram_id": member.telegram_id,
                "name": member.first_name or member.username or "Участник",
                "role": member.role.value,
                "is_current": member.id == user.id,
            }
            for member in members
        ]
    }


@router.post("/miniapp/transactions")
async def miniapp_add_transaction(
    payload: ManualTransactionCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await user_by_telegram_id(session, payload.telegram_id)
    tx, alerts = await finance.add_manual_transaction(
        session=session,
        user=user,
        amount=payload.amount,
        tx_type=payload.type,
        category_name=payload.category,
        operation_date=payload.date,
        comment=payload.comment,
        tag_name=payload.tag,
        is_personal=payload.is_personal,
    )
    return {
        "id": str(tx.id),
        "amount": str(tx.amount),
        "type": tx.type.value,
        "category": tx.category.name,
        "date": tx.date.isoformat(),
        "alerts": alerts,
    }


@router.get("/miniapp/transactions/{telegram_id}")
async def miniapp_transactions(
    telegram_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    category: str | None = None,
    scope: str | None = Query(default=None, pattern="^(personal|family)$"),
    tx_type: TransactionType | None = None,
    member_id: UUID | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    conditions = [Transaction.family_id == user.family_id]
    if date_from:
        conditions.append(Transaction.date >= date_from)
    if date_to:
        conditions.append(Transaction.date <= date_to)
    if tx_type:
        conditions.append(Transaction.type == tx_type)
    if scope == "personal":
        conditions.append(Transaction.is_personal.is_(True))
    elif scope == "family":
        conditions.append(Transaction.is_personal.is_(False))
    if category:
        conditions.append(Category.name == category)
    if member_id:
        member = await session.scalar(select(User.id).where(User.id == member_id, User.family_id == user.family_id))
        if not member:
            raise HTTPException(status_code=404, detail="Family member not found")
        conditions.append(Transaction.user_id == member_id)

    stmt = (
        select(Transaction)
        .join(Category, Category.id == Transaction.category_id)
        .options(selectinload(Transaction.category), selectinload(Transaction.tag), selectinload(Transaction.user))
        .where(and_(*conditions))
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .limit(200)
    )
    transactions = list((await session.scalars(stmt)).all())
    total_income = sum((tx.amount for tx in transactions if tx.type == TransactionType.income), 0)
    total_expense = sum((tx.amount for tx in transactions if tx.type == TransactionType.expense), 0)
    return {
        "items": [
            {
                "id": str(tx.id),
                "date": tx.date.isoformat(),
                "amount": str(tx.amount),
                "type": tx.type.value,
                "category": tx.category.name if tx.category else "Прочее",
                "emoji": tx.category.emoji if tx.category else "📦",
                "comment": tx.comment,
                "tag": tx.tag.name if tx.tag else None,
                "is_personal": tx.is_personal,
                "user": tx.user.first_name or tx.user.username or "Участник",
            }
            for tx in transactions
        ],
        "summary": {
            "income": str(total_income),
            "expense": str(total_expense),
            "balance": str(total_income - total_expense),
        },
    }


@router.get("/miniapp/budget-template/{telegram_id}")
async def miniapp_budget_template(
    telegram_id: int,
    month: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    try:
        target_month = datetime.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Month must be YYYY-MM") from exc
    values = await finance.budget_template_values(session, user.family_id, target_month)
    items = []
    for name, emoji, _keywords in EXPENSE_CATEGORIES:
        if name == "Прочее":
            continue
        items.append({"category": name, "emoji": emoji, "amount": str(values.get(name, 0))})
    return {"month": month, "items": items}


@router.post("/miniapp/budget-plan")
async def miniapp_save_budget_plan(
    payload: BudgetPlanCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    user = await user_by_telegram_id(session, payload.telegram_id)
    items = [(item.category, item.amount) for item in payload.items]
    await finance.set_budget_plan(session, user.family_id, payload.month, items)
    total = sum((item.amount for item in payload.items), 0)
    return {"month": payload.month.strftime("%Y-%m"), "categories": len(items), "total": str(total)}


@router.post("/expense")
async def add_expense(payload: OperationCreate, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, payload.telegram_id)
    tx, alerts = await finance.add_from_text(session, user, payload.text, TransactionType.expense)
    return {
        "id": str(tx.id),
        "type": tx.type,
        "amount": str(tx.amount),
        "category": tx.category.name,
        "comment": tx.comment,
        "alerts": alerts,
    }


@router.post("/income")
async def add_income(payload: OperationCreate, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, payload.telegram_id)
    tx, alerts = await finance.add_from_text(session, user, payload.text, TransactionType.income)
    return {
        "id": str(tx.id),
        "type": tx.type,
        "amount": str(tx.amount),
        "category": tx.category.name,
        "comment": tx.comment,
        "alerts": alerts,
    }


@router.post("/budget")
async def set_budget(payload: BudgetCreate, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, payload.telegram_id)
    budget = await finance.set_budget(session, user.family_id, payload.category, payload.amount)
    return {"category_id": str(budget.category_id), "limit_amount": str(budget.limit_amount)}


@router.get("/budget/{telegram_id}")
async def get_budget(telegram_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    rows = await finance.budget_rows(session, user.family_id)
    return {
        "items": [
            {
                "category": row["category"].name,
                "limit": str(row["limit"]),
                "spent": str(row["spent"]),
                "left": str(row["left"]),
                "percent": float(row["percent"]),
            }
            for row in rows
        ]
    }


@router.get("/analytics/{telegram_id}")
async def get_analytics(telegram_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    summary = await analytics.period_summary(session, user.family_id, 30)
    categories = await analytics.category_expenses(session, user.family_id, 30)
    months = await analytics.monthly_compare(session, user.family_id)
    return {
        "summary": {key: money(value) for key, value in summary.items()},
        "categories": [{"name": name, "amount": str(amount)} for name, amount in categories],
        "months": [{**row, "income": str(row["income"]), "expense": str(row["expense"])} for row in months],
    }


@router.post("/goals")
async def create_goal(payload: GoalCreate, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, payload.telegram_id)
    goal = await finance.add_goal(session, user.family_id, payload.title, payload.target_amount, payload.due_date)
    return {"id": str(goal.id), "title": goal.title, "target_amount": str(goal.target_amount)}


@router.get("/goals/{telegram_id}")
async def list_goals(telegram_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    goals = await finance.list_goals(session, user.family_id)
    return {
        "items": [
            {
                "id": str(goal.id),
                "title": goal.title,
                "target_amount": str(goal.target_amount),
                "current_amount": str(goal.current_amount),
            }
            for goal in goals
        ]
    }


@router.get("/reports/{telegram_id}")
async def get_report(telegram_id: int, period: str = "monthly", session: AsyncSession = Depends(get_session)) -> dict:
    user = await user_by_telegram_id(session, telegram_id)
    return {"period": period, "text": await reports.text_report(session, user.family_id, period)}
