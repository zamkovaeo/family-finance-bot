from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Select, and_, extract, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import Budget, Category, Goal, Tag, Transaction, User
from app.models.enums import CategoryKind, TransactionType
from app.services.llm_service import Categorizer
from app.services.parser import ParsedOperation, parse_operation


def month_start(dt: datetime | None = None) -> datetime:
    current = dt or datetime.now(timezone.utc)
    return datetime(current.year, current.month, 1, tzinfo=timezone.utc)


class FinanceService:
    def __init__(self) -> None:
        self.categorizer = Categorizer()

    async def add_from_text(
        self,
        session: AsyncSession,
        user: User,
        text: str,
        default_type: TransactionType,
    ) -> tuple[Transaction, list[str]]:
        parsed = parse_operation(text, default_type)
        return await self.add_transaction(session, user, parsed)

    async def add_transaction(
        self,
        session: AsyncSession,
        user: User,
        parsed: ParsedOperation,
    ) -> tuple[Transaction, list[str]]:
        kind = CategoryKind.expense if parsed.type == TransactionType.expense else CategoryKind.income
        category = await self.categorizer.choose_category(session, user.family_id, parsed.comment, kind)
        tag = await self._get_or_create_tag(session, user.family_id, parsed.tag)

        tx = Transaction(
            date=parsed.date or datetime.now(timezone.utc),
            amount=parsed.amount,
            type=parsed.type,
            user_id=user.id,
            family_id=user.family_id,
            category_id=category.id,
            tag_id=tag.id if tag else None,
            comment=parsed.comment,
            is_personal=parsed.is_personal,
        )
        session.add(tx)
        await session.flush()
        alerts = await self.check_limit_alerts(session, user.family_id, category.id, tx.date)
        await session.commit()
        await session.refresh(tx, attribute_names=["category", "tag"])
        return tx, alerts

    async def set_budget(
        self,
        session: AsyncSession,
        family_id,
        category_name: str,
        amount: Decimal,
    ) -> Budget:
        category = await session.scalar(
            select(Category).where(
                Category.family_id == family_id,
                Category.kind == CategoryKind.expense,
                func.lower(Category.name) == category_name.lower(),
            )
        )
        if not category:
            raise ValueError("Категория не найдена. Проверьте название.")

        stmt = insert(Budget).values(
            family_id=family_id,
            category_id=category.id,
            month=month_start(),
            limit_amount=amount,
            notified_80=False,
            notified_100=False,
            notified_over=False,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_budget_month",
            set_={"limit_amount": amount, "notified_80": False, "notified_100": False, "notified_over": False},
        ).returning(Budget)
        budget = (await session.execute(stmt)).scalar_one()
        await session.commit()
        return budget

    async def budget_rows(self, session: AsyncSession, family_id, user_id=None, personal_only: bool = False) -> list[dict]:
        start = month_start()
        tx_conditions = [
            Transaction.category_id == Budget.category_id,
            Transaction.family_id == family_id,
            Transaction.type == TransactionType.expense,
            extract("year", Transaction.date) == start.year,
            extract("month", Transaction.date) == start.month,
        ]
        if personal_only and user_id:
            tx_conditions.extend([Transaction.user_id == user_id, Transaction.is_personal.is_(True)])

        stmt = (
            select(
                Budget,
                Category,
                func.coalesce(func.sum(Transaction.amount), 0).label("spent"),
            )
            .join(Category, Category.id == Budget.category_id)
            .outerjoin(
                Transaction,
                and_(*tx_conditions),
            )
            .where(Budget.family_id == family_id, Budget.month == start)
            .group_by(Budget.id, Category.id)
            .order_by(Category.name)
        )
        rows = []
        for budget, category, spent in (await session.execute(stmt)).all():
            spent = Decimal(spent)
            limit = Decimal(budget.limit_amount)
            percent = (spent / limit * 100) if limit else Decimal(0)
            rows.append(
                {
                    "category": category,
                    "limit": limit,
                    "spent": spent,
                    "left": limit - spent,
                    "percent": percent,
                }
            )
        return rows

    async def family_balance(self, session: AsyncSession, family_id) -> dict[str, Decimal]:
        stmt = (
            select(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.family_id == family_id)
            .group_by(Transaction.type)
        )
        values = {TransactionType.income: Decimal(0), TransactionType.expense: Decimal(0)}
        for tx_type, amount in (await session.execute(stmt)).all():
            values[tx_type] = Decimal(amount)
        return {
            "income": values[TransactionType.income],
            "expense": values[TransactionType.expense],
            "balance": values[TransactionType.income] - values[TransactionType.expense],
        }

    async def check_limit_alerts(self, session: AsyncSession, family_id, category_id, operation_date: datetime | None = None) -> list[str]:
        operation_month = month_start(operation_date)
        if operation_month != month_start():
            return []
        budget = await session.scalar(
            select(Budget)
            .options(selectinload(Budget.category))
            .where(Budget.family_id == family_id, Budget.category_id == category_id, Budget.month == operation_month)
        )
        if not budget:
            return []

        spent = await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.family_id == family_id,
                Transaction.category_id == category_id,
                Transaction.type == TransactionType.expense,
                extract("year", Transaction.date) == operation_month.year,
                extract("month", Transaction.date) == operation_month.month,
            )
        )
        spent = Decimal(spent)
        percent = spent / Decimal(budget.limit_amount) * 100 if budget.limit_amount else Decimal(0)
        alerts = []
        category_name = budget.category.name
        if percent >= 80 and not budget.notified_80:
            budget.notified_80 = True
            alerts.append(f"Достигнуто 80% лимита по категории {category_name}.")
        if percent >= 100 and not budget.notified_100:
            budget.notified_100 = True
            alerts.append(f"Лимит по категории {category_name} исчерпан.")
        if percent > 100 and not budget.notified_over:
            budget.notified_over = True
            alerts.append(f"Превышение лимита по категории {category_name}: {percent:.0f}%.")
        return alerts

    async def add_goal(
        self,
        session: AsyncSession,
        family_id,
        title: str,
        target_amount: Decimal,
        due_date=None,
    ) -> Goal:
        goal = Goal(family_id=family_id, title=title, target_amount=target_amount, due_date=due_date)
        session.add(goal)
        await session.commit()
        await session.refresh(goal)
        return goal

    async def add_goal_progress(self, session: AsyncSession, family_id, title: str, amount: Decimal) -> Goal:
        goal = await session.scalar(
            select(Goal).where(Goal.family_id == family_id, func.lower(Goal.title) == title.lower())
        )
        if not goal:
            raise ValueError("Цель не найдена.")
        goal.current_amount += amount
        await session.commit()
        await session.refresh(goal)
        return goal

    async def list_goals(self, session: AsyncSession, family_id) -> list[Goal]:
        return list((await session.scalars(select(Goal).where(Goal.family_id == family_id).order_by(Goal.created_at))).all())

    async def _get_or_create_tag(self, session: AsyncSession, family_id, tag_name: str | None) -> Tag | None:
        if not tag_name:
            return None
        tag = await session.scalar(select(Tag).where(Tag.family_id == family_id, Tag.name == tag_name))
        if tag:
            return tag
        tag = Tag(family_id=family_id, name=tag_name)
        session.add(tag)
        await session.flush()
        return tag
