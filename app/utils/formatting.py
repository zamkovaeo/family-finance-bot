from decimal import Decimal


def money(value: Decimal | int | float, currency: str = "RUB") -> str:
    amount = Decimal(value)
    suffix = "₽" if currency == "RUB" else currency
    return f"{amount:,.0f}".replace(",", " ") + f" {suffix}"


def progress_bar(percent: Decimal | float, width: int = 12) -> str:
    value = min(max(float(percent), 0), 100)
    filled = round(value / 100 * width)
    return "█" * filled + "░" * (width - filled)


def percent_text(value: Decimal | float) -> str:
    return f"{float(value):.0f}%"

