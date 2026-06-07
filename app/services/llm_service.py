from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import Category
from app.models.enums import CategoryKind
from app.services.defaults import category_defaults


class Categorizer:
    """Categorizes operations.

    MVP works without a paid LLM key by using local keyword rules. If OPENAI_API_KEY is
    configured, this class can later be extended to call the selected LLM model while
    preserving the same public method.
    """

    async def choose_category(
        self,
        session: AsyncSession,
        family_id,
        text: str,
        kind: CategoryKind,
    ) -> Category:
        text_lower = text.lower()
        selected_name = "Прочее"

        selected_emoji = "📦" if kind == CategoryKind.expense else "💰"
        for name, emoji, keywords in category_defaults(kind):
            if any(keyword in text_lower for keyword in keywords):
                selected_name = name
                selected_emoji = emoji
                break

        category = await session.scalar(
            select(Category).where(
                Category.family_id == family_id,
                Category.kind == kind,
                Category.name == selected_name,
            )
        )
        if category:
            return category

        category = Category(
            family_id=family_id,
            name=selected_name,
            kind=kind,
            emoji=selected_emoji,
            is_default=True,
        )
        session.add(category)
        await session.flush()
        return category

        fallback = await session.scalar(
            select(Category).where(
                Category.family_id == family_id,
                Category.kind == kind,
                Category.name == "Прочее",
            )
        )
        if not fallback:
            raise RuntimeError("Не найдены категории семьи. Перезапустите регистрацию.")
        return fallback


async def transcribe_voice(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    if not settings.openai_api_key:
        raise RuntimeError("Распознавание голоса требует OPENAI_API_KEY в .env")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    result = await client.audio.transcriptions.create(
        model=settings.stt_model,
        file=(filename, file_bytes),
        language="ru",
    )
    return result.text
