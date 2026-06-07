from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, Message
from sqlalchemy import select

from app.bot.keyboards import analytics_menu, goals_menu, main_menu, settings_menu
from app.db.session import SessionLocal
from app.models.entities import Family, User
from app.models.enums import TransactionType
from app.services.analytics_service import AnalyticsService
from app.services.family_service import ensure_user
from app.services.finance_service import FinanceService
from app.services.llm_service import transcribe_voice
from app.services.reporting_service import ReportingService
from app.utils.formatting import money, percent_text, progress_bar

router = Router()
finance = FinanceService()
analytics = AnalyticsService()
reports = ReportingService()


class InputState(StatesGroup):
    expense = State()
    income = State()
    budget = State()
    goal_create = State()
    goal_progress = State()


async def current_user(message: Message, invite_code: str | None = None) -> User:
    async with SessionLocal() as session:
        user = await ensure_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            invite_code=invite_code,
        )
        return user


@router.message(Command("start"))
async def start(message: Message, command: CommandObject) -> None:
    user = await current_user(message, command.args)
    async with SessionLocal() as session:
        family = await session.get(Family, user.family_id)
    role_text = "администратор" if user.role.value == "admin" else "участник"
    await message.answer(
        "Готов вести семейный бюджет.\n\n"
        f"Ваша роль: {role_text}\n"
        f"Код приглашения семьи: {family.invite_code}\n\n"
        "Можно писать сразу: Кофе 350 #отпуск личное 07.06.2026",
        reply_markup=main_menu(),
    )


@router.message(F.text == "⬅️ Главное меню")
async def back_to_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_menu())


@router.message(F.text == "➕ Расход")
async def ask_expense(message: Message, state: FSMContext) -> None:
    await current_user(message)
    await state.set_state(InputState.expense)
    await message.answer("Введите расход: Кофе 350 #отпуск личное 07.06.2026")


@router.message(F.text == "💰 Доход")
async def ask_income(message: Message, state: FSMContext) -> None:
    await current_user(message)
    await state.set_state(InputState.income)
    await message.answer("Введите доход: Зарплата 180000 01.06.2026")


@router.message(InputState.expense)
async def save_expense(message: Message, state: FSMContext, bot: Bot) -> None:
    await add_operation(message, bot, TransactionType.expense)
    await state.clear()


@router.message(InputState.income)
async def save_income(message: Message, state: FSMContext, bot: Bot) -> None:
    await add_operation(message, bot, TransactionType.income)
    await state.clear()


@router.message(F.text == "📊 Мой бюджет")
@router.message(F.text == "👨‍👩‍👧 Семейный бюджет")
async def show_budget(message: Message) -> None:
    user = await current_user(message)
    personal_only = message.text.startswith("📊")
    async with SessionLocal() as session:
        rows = await finance.budget_rows(session, user.family_id, user.id, personal_only)
        balance = await finance.family_balance(session, user.family_id)

    if not rows:
        await message.answer(
            "Лимиты на текущий месяц пока не заданы.\n\n"
            "Откройте Настройки → Задать лимит и введите: Продукты 60000",
            reply_markup=main_menu(),
        )
        return

    lines = ["Мой бюджет" if personal_only else "Семейный бюджет", ""]
    for row in rows:
        lines.append(
            f"{row['category'].emoji} {row['category'].name}: {progress_bar(row['percent'])} "
            f"{percent_text(row['percent'])}\n"
            f"План {money(row['limit'])} · факт {money(row['spent'])} · остаток {money(row['left'])}"
        )
    lines.append("")
    lines.append(f"Всего: доходы {money(balance['income'])}, расходы {money(balance['expense'])}, баланс {money(balance['balance'])}")
    await message.answer("\n\n".join(lines), reply_markup=main_menu())


@router.message(F.text == "📈 Отчеты и аналитика")
async def open_analytics(message: Message) -> None:
    await current_user(message)
    await message.answer("Отчеты и аналитика", reply_markup=analytics_menu())


@router.message(F.text.in_({"Дневной отчет", "Недельный отчет", "Месячный отчет"}))
async def report_text(message: Message) -> None:
    user = await current_user(message)
    period = {"Дневной отчет": "daily", "Недельный отчет": "weekly", "Месячный отчет": "monthly"}[message.text]
    async with SessionLocal() as session:
        text = await reports.text_report(session, user.family_id, period)
    await message.answer(text, reply_markup=analytics_menu())


@router.message(F.text.in_({"Круговая диаграмма", "График по дням", "Сравнение месяцев"}))
async def chart(message: Message) -> None:
    user = await current_user(message)
    async with SessionLocal() as session:
        if message.text == "Круговая диаграмма":
            image = await analytics.pie_chart(session, user.family_id)
            caption = "Расходы по категориям"
        elif message.text == "График по дням":
            image = await analytics.line_chart(session, user.family_id)
            caption = "Динамика расходов"
        else:
            image = await analytics.stacked_months_chart(session, user.family_id)
            caption = "Доходы и расходы по месяцам"
    await message.answer_photo(BufferedInputFile(image.read(), filename="analytics.png"), caption=caption, reply_markup=analytics_menu())


@router.message(F.text == "🎯 Цели")
async def open_goals(message: Message) -> None:
    await current_user(message)
    await message.answer("Цели", reply_markup=goals_menu())


@router.message(F.text == "Список целей")
async def list_goals(message: Message) -> None:
    user = await current_user(message)
    async with SessionLocal() as session:
        goals = await finance.list_goals(session, user.family_id)
    if not goals:
        await message.answer("Целей пока нет. Нажмите «Добавить цель».", reply_markup=goals_menu())
        return
    lines = ["Цели семьи", ""]
    for goal in goals:
        percent = goal.current_amount / goal.target_amount * 100 if goal.target_amount else 0
        lines.append(
            f"🎯 {goal.title}: {progress_bar(percent)} {percent_text(percent)}\n"
            f"{money(goal.current_amount)} из {money(goal.target_amount)}"
        )
    await message.answer("\n\n".join(lines), reply_markup=goals_menu())


@router.message(F.text == "Добавить цель")
async def ask_goal(message: Message, state: FSMContext) -> None:
    await state.set_state(InputState.goal_create)
    await message.answer("Введите цель: Отпуск 300000")


@router.message(InputState.goal_create)
async def create_goal(message: Message, state: FSMContext) -> None:
    user = await current_user(message)
    try:
        title, amount = split_title_amount(message.text)
        async with SessionLocal() as session:
            goal = await finance.add_goal(session, user.family_id, title, amount)
        await message.answer(f"Цель создана: {goal.title}, {money(goal.target_amount)}", reply_markup=goals_menu())
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()


@router.message(F.text == "Пополнить цель")
async def ask_goal_progress(message: Message, state: FSMContext) -> None:
    await state.set_state(InputState.goal_progress)
    await message.answer("Введите пополнение: Отпуск 15000")


@router.message(InputState.goal_progress)
async def goal_progress(message: Message, state: FSMContext) -> None:
    user = await current_user(message)
    try:
        title, amount = split_title_amount(message.text)
        async with SessionLocal() as session:
            goal = await finance.add_goal_progress(session, user.family_id, title, amount)
        await message.answer(f"Пополнено: {goal.title}. Сейчас {money(goal.current_amount)}", reply_markup=goals_menu())
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message) -> None:
    await current_user(message)
    await message.answer("Настройки", reply_markup=settings_menu())


@router.message(F.text == "Код семьи")
async def invite_code(message: Message) -> None:
    user = await current_user(message)
    async with SessionLocal() as session:
        family = await session.get(Family, user.family_id)
    await message.answer(
        f"Код семьи: {family.invite_code}\n\n"
        f"Чтобы присоединиться, новый участник пишет боту:\n/start {family.invite_code}",
        reply_markup=settings_menu(),
    )


@router.message(F.text == "Задать лимит")
async def ask_budget(message: Message, state: FSMContext) -> None:
    await state.set_state(InputState.budget)
    await message.answer("Введите лимит на месяц: Продукты 60000")


@router.message(InputState.budget)
async def set_budget(message: Message, state: FSMContext) -> None:
    user = await current_user(message)
    try:
        category, amount = split_title_amount(message.text)
        async with SessionLocal() as session:
            await finance.set_budget(session, user.family_id, category, amount)
        await message.answer(f"Лимит задан: {category} — {money(amount)}", reply_markup=settings_menu())
    except ValueError as exc:
        await message.answer(str(exc))
        return
    await state.clear()


@router.message(F.voice)
async def voice(message: Message, bot: Bot) -> None:
    await current_user(message)
    file = await bot.get_file(message.voice.file_id)
    data = await bot.download_file(file.file_path)
    try:
        text = await transcribe_voice(data.read(), "voice.ogg")
    except RuntimeError as exc:
        await message.answer(f"{exc}\n\nПока можно ввести операцию текстом.")
        return
    await message.answer(f"Распознал: {text}")
    await add_operation(message, bot, TransactionType.expense, text_override=text)


@router.message(F.text)
async def free_text_operation(message: Message, bot: Bot) -> None:
    if message.text.startswith("/"):
        return
    await add_operation(message, bot, TransactionType.expense)


async def add_operation(
    message: Message,
    bot: Bot,
    default_type: TransactionType,
    text_override: str | None = None,
) -> None:
    user = await current_user(message)
    text = text_override or message.text or ""
    try:
        async with SessionLocal() as session:
            tx, alerts = await finance.add_from_text(session, user, text, default_type)
            family_users = list((await session.scalars(select(User).where(User.family_id == user.family_id))).all())
    except ValueError as exc:
        await message.answer(str(exc), reply_markup=main_menu())
        return

    sign = "Доход" if tx.type == TransactionType.income else "Расход"
    scope = "личное" if tx.is_personal else "семейное"
    tag = f" · #{tx.tag.name}" if tx.tag else ""
    await message.answer(
        f"{sign} сохранен\n\n"
        f"{tx.category.emoji} {tx.category.name}: {money(tx.amount)}\n"
        f"{tx.comment} · {scope}{tag}\n"
        f"Дата: {tx.date:%d.%m.%Y}",
        reply_markup=main_menu(),
    )
    for alert in alerts:
        for member in family_users:
            await bot.send_message(member.telegram_id, f"⚠️ {alert}")


def split_title_amount(text: str) -> tuple[str, Decimal]:
    parts = text.rsplit(" ", 1)
    if len(parts) != 2:
        raise ValueError("Нужен формат: Название 10000")
    title, raw_amount = parts[0].strip(), parts[1].replace(",", ".")
    if not title:
        raise ValueError("Не вижу название.")
    try:
        amount = Decimal(raw_amount)
    except Exception as exc:
        raise ValueError("Не вижу сумму.") from exc
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    return title, amount
