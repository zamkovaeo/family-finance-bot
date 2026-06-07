from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Расход"), KeyboardButton(text="💰 Доход")],
            [KeyboardButton(text="📊 Мой бюджет"), KeyboardButton(text="👨‍👩‍👧 Семейный бюджет")],
            [KeyboardButton(text="📈 Отчеты и аналитика"), KeyboardButton(text="🎯 Цели")],
            [KeyboardButton(text="⚙️ Настройки")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Например: Кофе 350 #отпуск личное",
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

