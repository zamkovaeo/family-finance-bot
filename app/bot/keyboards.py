from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.core.config import settings


def mini_app_url(telegram_id: int | None = None) -> str:
    if not settings.public_app_url or telegram_id is None:
        return settings.public_app_url
    separator = "&" if "?" in settings.public_app_url else "?"
    return f"{settings.public_app_url}{separator}telegram_id={telegram_id}"


def main_menu(telegram_id: int | None = None) -> ReplyKeyboardMarkup:
    mini_app_button = KeyboardButton(
        text="🚀 Открыть Mini App",
        web_app=WebAppInfo(url=mini_app_url(telegram_id)) if settings.public_app_url else None,
    )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Расход"), KeyboardButton(text="💰 Доход")],
            [mini_app_button],
        ],
        resize_keyboard=True,
        input_field_placeholder="Быстрый ввод: Кофе 350",
    )


def analytics_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Дневной отчет"), KeyboardButton(text="Недельный отчет"), KeyboardButton(text="Месячный отчет")],
            [KeyboardButton(text="Круговая диаграмма"), KeyboardButton(text="График по дням")],
            [KeyboardButton(text="Сравнение месяцев"), KeyboardButton(text="⬅️ Главное меню")],
        ],
        resize_keyboard=True,
    )


def goals_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Список целей"), KeyboardButton(text="Добавить цель")],
            [KeyboardButton(text="Пополнить цель"), KeyboardButton(text="⬅️ Главное меню")],
        ],
        resize_keyboard=True,
    )


def settings_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Задать лимит"), KeyboardButton(text="Код семьи")],
            [KeyboardButton(text="⬅️ Главное меню")],
        ],
        resize_keyboard=True,
    )
