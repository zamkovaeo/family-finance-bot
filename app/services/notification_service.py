import asyncio
import json
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import Family, Report, User
from app.services.reporting_service import ReportingService


class NotificationService:
    """Sends scheduled family reports.

    The MVP uses a lightweight async loop, which is enough for a single service.
    In production this can move to Celery, APScheduler, or a managed cron worker
    without changing report generation itself.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.reporting = ReportingService()

    async def run(self) -> None:
        while True:
            await self.tick()
            await asyncio.sleep(3600)

    async def tick(self) -> None:
        now = datetime.now(timezone.utc)
        if now.weekday() == 0:
            await self._send_period_once("weekly", f"weekly:{now:%Y-%W}")
        if self._is_last_day(now):
            await self._send_period_once("monthly", f"monthly:{now:%Y-%m}")

    async def _send_period_once(self, period: str, report_key: str) -> None:
        async with SessionLocal() as session:
            families = list((await session.scalars(select(Family))).all())
            for family in families:
                exists = await session.scalar(
                    select(Report).where(Report.family_id == family.id, Report.period == report_key)
                )
                if exists:
                    continue
                text = await self.reporting.text_report(session, family.id, period)
                users = list((await session.scalars(select(User).where(User.family_id == family.id))).all())
                for user in users:
                    await self.bot.send_message(user.telegram_id, text)
                session.add(
                    Report(
                        family_id=family.id,
                        period=report_key,
                        payload=json.dumps({"sent_to": [user.telegram_id for user in users]}, ensure_ascii=False),
                    )
                )
            await session.commit()

    def _is_last_day(self, now: datetime) -> bool:
        return (now + timedelta(days=1)).month != now.month


async def run_notifications(bot: Bot) -> None:
    await NotificationService(bot).run()
