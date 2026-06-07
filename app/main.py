import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.bot.app import create_bot, run_bot
from app.core.config import settings
from app.services.notification_service import run_notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = None
    notification_task = None
    if settings.telegram_bot_token:
        bot_task = asyncio.create_task(run_bot())
        notification_task = asyncio.create_task(run_notifications(create_bot()))
    yield
    for task in (bot_task, notification_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
