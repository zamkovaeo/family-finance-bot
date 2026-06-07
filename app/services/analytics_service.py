from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Category, Transaction
from app.models.enums import TransactionType


class AnalyticsService:
    async def period_summary(self, session: AsyncSession, family_id, days: int) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(Transaction.type, func.coalesce(func.sum(Transaction.amount), 0))
            .where(Transaction.family_id == family_id, Transaction.date >= since)
            .group_by(Transaction.type)
        )
        result = {TransactionType.income: Decimal(0), TransactionType.expense: Decimal(0)}
        for tx_type, amount in (await session.execute(stmt)).all():
            result[tx_type] = Decimal(amount)
        return {
            "income": result[TransactionType.income],
            "expense": result[TransactionType.expense],
            "balance": result[TransactionType.income] - result[TransactionType.expense],
        }

    async def category_expenses(self, session: AsyncSession, family_id, days: int = 30) -> list[tuple[str, Decimal]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(Category.name, func.coalesce(func.sum(Transaction.amount), 0))
            .join(Transaction, Transaction.category_id == Category.id)
            .where(
                Transaction.family_id == family_id,
                Transaction.type == TransactionType.expense,
                Transaction.date >= since,
            )
            .group_by(Category.name)
            .order_by(func.sum(Transaction.amount).desc())
        )
        return [(name, Decimal(amount)) for name, amount in (await session.execute(stmt)).all()]

    async def daily_expenses(self, session: AsyncSession, family_id, days: int = 30) -> list[tuple[str, Decimal]]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(func.date(Transaction.date), func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.family_id == family_id,
                Transaction.type == TransactionType.expense,
                Transaction.date >= since,
            )
            .group_by(func.date(Transaction.date))
            .order_by(func.date(Transaction.date))
        )
        return [(str(day), Decimal(amount)) for day, amount in (await session.execute(stmt)).all()]

    async def monthly_compare(self, session: AsyncSession, family_id, months: int = 6) -> list[dict]:
        stmt = (
            select(
                extract("year", Transaction.date).label("year"),
                extract("month", Transaction.date).label("month"),
                Transaction.type,
                func.coalesce(func.sum(Transaction.amount), 0),
            )
            .where(Transaction.family_id == family_id)
            .group_by("year", "month", Transaction.type)
            .order_by("year", "month")
        )
        rows = {}
        for year, month, tx_type, amount in (await session.execute(stmt)).all():
            key = f"{int(month):02d}.{int(year)}"
            rows.setdefault(key, {"month": key, "income": Decimal(0), "expense": Decimal(0)})
            rows[key][tx_type.value] = Decimal(amount)
        return list(rows.values())[-months:]

    async def pie_chart(self, session: AsyncSession, family_id) -> BytesIO:
        data = await self.category_expenses(session, family_id)
        return self._pie_chart(data)

    async def line_chart(self, session: AsyncSession, family_id) -> BytesIO:
        data = await self.daily_expenses(session, family_id)
        return self._line_chart(data)

    async def stacked_months_chart(self, session: AsyncSession, family_id) -> BytesIO:
        data = await self.monthly_compare(session, family_id)
        return self._stacked_chart(data)

    def _pie_chart(self, data: list[tuple[str, Decimal]]) -> BytesIO:
        fig, ax = plt.subplots(figsize=(7, 5))
        if data:
            labels, values = zip(*data)
            ax.pie([float(v) for v in values], labels=labels, autopct="%1.0f%%", startangle=90)
            ax.set_title("Расходы по категориям за 30 дней")
        else:
            ax.text(0.5, 0.5, "Пока нет расходов", ha="center", va="center")
            ax.axis("off")
        return self._save(fig)

    def _line_chart(self, data: list[tuple[str, Decimal]]) -> BytesIO:
        fig, ax = plt.subplots(figsize=(8, 4))
        if data:
            labels, values = zip(*data)
            ax.plot(labels, [float(v) for v in values], marker="o", color="#2f80ed")
            ax.tick_params(axis="x", rotation=45)
            ax.set_title("Расходы по дням")
            ax.grid(True, alpha=0.25)
        else:
            ax.text(0.5, 0.5, "Пока нет расходов", ha="center", va="center")
            ax.axis("off")
        return self._save(fig)

    def _stacked_chart(self, data: list[dict]) -> BytesIO:
        fig, ax = plt.subplots(figsize=(8, 4))
        if data:
            labels = [row["month"] for row in data]
            income = [float(row["income"]) for row in data]
            expense = [float(row["expense"]) for row in data]
            ax.bar(labels, income, label="Доходы", color="#27ae60")
            ax.bar(labels, expense, bottom=income, label="Расходы", color="#eb5757")
            ax.set_title("Сравнение месяцев")
            ax.legend()
        else:
            ax.text(0.5, 0.5, "Недостаточно данных", ha="center", va="center")
            ax.axis("off")
        return self._save(fig)

    def _save(self, fig) -> BytesIO:
        buffer = BytesIO()
        fig.tight_layout()
        fig.savefig(buffer, format="png", dpi=160)
        plt.close(fig)
        buffer.seek(0)
        return buffer

