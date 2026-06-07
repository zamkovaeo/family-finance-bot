import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Category, Family, User
from app.models.enums import CategoryKind, UserRole
from app.services.defaults import category_defaults


def make_invite_code() -> str:
    return secrets.token_hex(4).upper()


async def ensure_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    invite_code: str | None = None,
) -> User:
    existing = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if existing:
        return existing

    family = None
    role = UserRole.admin
    if invite_code:
        family = await session.scalar(select(Family).where(Family.invite_code == invite_code.upper()))
        role = UserRole.member if family else UserRole.admin

    if family is None:
        family = Family(name="Семейный бюджет", invite_code=make_invite_code())
        session.add(family)
        await session.flush()
        await seed_categories(session, family.id)

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        role=role,
        family_id=family.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def seed_categories(session: AsyncSession, family_id) -> None:
    for kind in (CategoryKind.expense, CategoryKind.income):
        for name, emoji, _keywords in category_defaults(kind):
            session.add(
                Category(
                    family_id=family_id,
                    name=name,
                    kind=kind,
                    emoji=emoji,
                    is_default=True,
                )
            )

