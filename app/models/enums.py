from enum import StrEnum


class UserRole(StrEnum):
    admin = "admin"
    member = "member"


class TransactionType(StrEnum):
    income = "income"
    expense = "expense"


class CategoryKind(StrEnum):
    income = "income"
    expense = "expense"

