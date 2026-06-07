from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import router
from app.core.config import settings


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    return dp


def create_bot() -> Bot:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    return Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=None))


async def run_bot() -> None:
    bot = create_bot()
    dp = create_dispatcher()
    await dp.start_polling(bot)
