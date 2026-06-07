import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from app.models.enums import TransactionType

AMOUNT_RE = re.compile(r"(?P<amount>\d+(?:[.,]\d{1,2})?)")
TAG_RE = re.compile(r"#(?P<tag>[\wа-яА-ЯёЁ-]+)")
DATE_PATTERNS = [
    re.compile(r"\b(?P<date>\d{4}-\d{1,2}-\d{1,2})\b"),
    re.compile(r"\b(?P<date>\d{1,2}[.\/-]\d{1,2}(?:[.\/-]\d{2,4})?)\b"),
]


@dataclass(slots=True)
class ParsedOperation:
    amount: Decimal
    comment: str
    tag: str | None
    is_personal: bool
    type: TransactionType
    date: datetime | None


def parse_operation(text: str, default_type: TransactionType) -> ParsedOperation:
    clean = text.strip()
    parsed_date, clean_without_date = extract_operation_date(clean)
    match = AMOUNT_RE.search(clean_without_date)
    if not match:
        raise ValueError("Не нашел сумму. Пример: Кофе 350 или Зарплата 180000")

    try:
        amount = Decimal(match.group("amount").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Сумма выглядит некорректно.") from exc

    tag_match = TAG_RE.search(clean)
    tag = tag_match.group("tag").lower() if tag_match else None
    is_personal = any(word in clean.lower() for word in ("личное", "личный", "личная", "personal"))

    comment = AMOUNT_RE.sub("", clean_without_date, count=1)
    comment = TAG_RE.sub("", comment)
    comment = re.sub(r"\b(личное|личный|личная|семейное|семейный|personal)\b", "", comment, flags=re.I)
    comment = " ".join(comment.split()) or ("Доход" if default_type == TransactionType.income else "Расход")

    lowered = clean.lower()
    op_type = default_type
    if any(word in lowered for word in ("доход", "зарплата", "аванс", "получил", "получила")):
        op_type = TransactionType.income
    if any(word in lowered for word in ("расход", "потратил", "потратила", "купил", "купила")):
        op_type = TransactionType.expense

    return ParsedOperation(
        amount=amount,
        comment=comment,
        tag=tag,
        is_personal=is_personal,
        type=op_type,
        date=parsed_date,
    )


def extract_operation_date(text: str) -> tuple[datetime | None, str]:
    lowered = text.lower()
    now = datetime.now(timezone.utc)

    relative_dates = {
        "сегодня": now,
        "вчера": now - timedelta(days=1),
        "позавчера": now - timedelta(days=2),
    }
    for word, value in relative_dates.items():
        if re.search(rf"\b{word}\b", lowered):
            clean = re.sub(rf"\b{word}\b", "", text, flags=re.I)
            return value.replace(hour=12, minute=0, second=0, microsecond=0), clean

    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group("date")
        parsed = parse_date(raw, now)
        clean = text[: match.start()] + text[match.end() :]
        return parsed, clean

    return None, text


def parse_date(raw: str, now: datetime) -> datetime:
    normalized = raw.replace("/", ".").replace("-", ".")
    parts = normalized.split(".")

    if len(parts) != 3:
        day, month = int(parts[0]), int(parts[1])
        year = now.year
    elif len(parts[0]) == 4:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
    else:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        if year < 100:
            year += 2000

    try:
        return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("Дата выглядит некорректно. Пример: 07.06.2026 или вчера.") from exc
