from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.ai.engine import ai_engine
from app.bot.sender import send_answer
from app.database.models import User
from app.memory.manager import memory_manager
from app.services.message_service import message_service
from app.services.user_service import user_service


router = Router(name="private")


@router.message(
    lambda message:
    message.chat.type == "private"
)
async def private_message(
    message: Message,
) -> None:

    if not message.from_user:
        return

    if message.text is None:
        return

    text = message.text.strip()

    if not text:
        return

    # ----------------------------------------------------------
    # USER
    # ----------------------------------------------------------

    user: User = await user_service.get_or_create(
        message.from_user
    )

    # ----------------------------------------------------------
    # USER MESSAGE
    # ----------------------------------------------------------

    saved_message = await message_service.save(
        chat_id=message.chat.id,
        telegram_message_id=message.message_id,
        user_telegram_id=user.telegram_id,
        role="user",
        content=text,
        message_type="text",
        reply_to_message_id=(
            message.reply_to_message.message_id
            if message.reply_to_message
            else None
        ),
        is_bot_message=False,
    )

    # ----------------------------------------------------------
    # AI
    # ----------------------------------------------------------

    answer = await ai_engine.generate(
        user_text=text,
        chat_id=message.chat.id,
        user_id=user.telegram_id,
        group_id=None,
    )

    # ----------------------------------------------------------
    # SAVE AI MESSAGE
    # ----------------------------------------------------------

    await message_service.save(
        chat_id=message.chat.id,
        telegram_message_id=None,
        user_telegram_id=user.telegram_id,
        role="assistant",
        content=answer,
        message_type="text",
        is_bot_message=True,
    )

    # ----------------------------------------------------------
    # SEND
    # ----------------------------------------------------------

    await send_answer(
        bot=message.bot,
        chat_id=message.chat.id,
        text=answer,
        reply_to_message_id=message.message_id,
  )
