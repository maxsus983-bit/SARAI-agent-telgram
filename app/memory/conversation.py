from __future__ import annotations

from sqlalchemy import select

from app.database.models import Message
from app.database.session import SessionFactory


async def get_recent_messages(
    chat_id: int,
    limit: int = 100,
) -> list[Message]:

    limit = max(1, min(limit, 200))

    async with SessionFactory() as session:

        query = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )

        result = await session.execute(query)

        messages = list(result.scalars().all())

        # AI uchun eski → yangi tartib.
        messages.reverse()

        return messages


async def build_conversation_context(
    chat_id: int,
    limit: int = 100,
) -> str:

    messages = await get_recent_messages(
        chat_id=chat_id,
        limit=limit,
    )

    if not messages:
        return "Suhbat tarixi mavjud emas."

    lines: list[str] = []

    for message in messages:

        role = message.role.upper()

        content = message.content.strip()

        if not content:
            continue

        lines.append(
            f"{role}: {content}"
        )

    return "\n".join(lines)
