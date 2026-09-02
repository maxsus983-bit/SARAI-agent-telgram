from __future__ import annotations

from typing import Optional

from app.database.models import Message
from app.database.session import SessionFactory


class MessageService:

    async def save(
        self,
        *,
        chat_id: int,
        content: str,
        role: str,
        telegram_message_id: Optional[int] = None,
        user_telegram_id: Optional[int] = None,
        message_type: str = "text",
        reply_to_message_id: Optional[int] = None,
        is_bot_message: bool = False,
    ) -> Message:

        async with SessionFactory() as session:

            message = Message(
                telegram_message_id=telegram_message_id,
                chat_id=chat_id,
                user_telegram_id=user_telegram_id,
                role=role,
                content=content,
                message_type=message_type,
                reply_to_message_id=reply_to_message_id,
                is_bot_message=is_bot_message,
            )

            session.add(message)

            await session.commit()
            await session.refresh(message)

            return message


message_service = MessageService()
