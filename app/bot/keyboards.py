from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from app.core.config import settings


def main_menu() -> ReplyKeyboardMarkup:
    mini_app_button = KeyboardButton(
        text="🚀 Открыть Mini App",
        web_app=WebAppInfo(url=settings.public_app_url) if settings.public_app_url else None,
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
