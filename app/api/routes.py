from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.entities import User
from app.models.enums import TransactionType
from app.schemas.finance import BudgetCreate, GoalCreate, OperationCreate
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

