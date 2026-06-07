from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics_service import AnalyticsService
from app.utils.formatting import money


class ReportingService:
    def __init__(self) -> None:
        self.analytics = AnalyticsService()

    async def text_report(self, session: AsyncSession, family_id, period: str) -> str:
        days = {"daily": 1, "weekly": 7, "monthly": 30}.get(period, 30)
        title = {"daily": "Ежедневный отчет", "weekly": "Недельный отчет", "monthly": "Месячный отчет"}.get(
            period, "Отчет"
        )
        summary = await self.analytics.period_summary(session, family_id, days)
        categories = await self.analytics.category_expenses(session, family_id, days)
        top = "\n".join(f"• {name}: {money(amount)}" for name, amount in categories[:7]) or "• Расходов пока нет"
        return (
            f"{title}\n\n"
            f"Доходы: {money(summary['income'])}\n"
            f"Расходы: {money(summary['expense'])}\n"
            f"Итог: {money(summary['balance'])}\n\n"
            f"Категории:\n{top}"
        )

