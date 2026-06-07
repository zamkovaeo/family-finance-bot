import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.models.enums import TransactionType

AMOUNT_RE = re.compile(r"(?P<amount>\d+(?:[.,]\d{1,2})?)")
TAG_RE = re.compile(r"#(?P<tag>[\wа-яА-ЯёЁ-]+)")


@dataclass(slots=True)
class ParsedOperation:
    amount: Decimal
    comment: str
    tag: str | None
    is_personal: bool
    type: TransactionType


def parse_operation(text: str, default_type: TransactionType) -> ParsedOperation:
    clean = text.strip()
    match = AMOUNT_RE.search(clean)
    if not match:
        raise ValueError("Не нашел сумму. Пример: Кофе 350 или Зарплата 180000")

    try:
        amount = Decimal(match.group("amount").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("Сумма выглядит некорректно.") from exc

    tag_match = TAG_RE.search(clean)
    tag = tag_match.group("tag").lower() if tag_match else None
    is_personal = any(word in clean.lower() for word in ("личное", "личный", "личная", "personal"))

    comment = AMOUNT_RE.sub("", clean, count=1)
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
    )

