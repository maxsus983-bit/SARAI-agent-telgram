from __future__ import annotations

import re

from aiogram import Router
from aiogram.types import Message

from app.ai.engine import ai_engine
from app.bot.sender import send_answer
from app.services.group_service import group_service
from app.services.message_service import message_service
from app.services.user_service import user_service


router = Router(name="groups")


def clean_mention(
    text: str,
    bot_username: str | None,
) -> str:

    if not bot_username:
        return text.strip()

    pattern = rf"@{re.escape(bot_username)}"

    return re.sub(
        pattern,
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def is_sara_called(
    message: Message,
) -> bool:

    if not message.text:
        return False

    text = message.text.lower()

    # Bot username orqali chaqirish.
    if message.entities:

        for entity in message.entities:

            if entity.type == "mention":

                mention = message.text[
                    entity.offset:
                    entity.offset + entity.length
                ]

                if (
                    message.bot.username
                    and mention.lower()
                    == f"@{message.bot.username}".lower()
                ):
                    return True

    # SARA nomi.
    words = re.findall(
        r"\b[\w'-]+\b",
        text,
    )

    if "sara" in words:
        return True

    # Botga reply.
    if message.reply_to_message:
        replied = message.reply_to_message

        if replied.from_user:

            if replied.from_user.id == message.bot.id:
                return True

    return False


@router.message(
    lambda message:
    message.chat.type in {
        "group",
        "supergroup",
    }
)
async def group_message(
    message: Message,
) -> None:

    if not message.from_user:
        return

    if not message.text:
        return

    # ----------------------------------------------------------
    # GROUP
    # ----------------------------------------------------------

    group = await group_service.get_or_create(
        message.chat
    )

    if not group.enabled:
        return

    # ----------------------------------------------------------
    # MESSAGE
    # ----------------------------------------------------------

    await message_service.save(
        chat_id=message.chat.id,
        telegram_message_id=message.message_id,
        user_telegram_id=message.from_user.id,
        role="user",
        content=message.text,
        message_type="text",
        reply_to_message_id=(
            message.reply_to_message.message_id
            if message.reply_to_message
            else None
        ),
        is_bot_message=False,
    )

    # SARA chaqirilmagan bo'lsa,
    # xabar database'da qoladi,
    # lekin javob bermaydi.

    if not is_sara_called(message):
        return

    # ----------------------------------------------------------
    # USER
    # ----------------------------------------------------------

    user = await user_service.get_or_create(
        message.from_user
    )

    # ----------------------------------------------------------
    # REMOVE MENTION
    # ----------------------------------------------------------

    text = clean_mention(
        message.text,
        message.bot.username,
    )

    if not text:
        text = "Salom SARA"

    # ----------------------------------------------------------
    # AI
    # ----------------------------------------------------------

    answer = await ai_engine.generate(
        user_text=text,
        chat_id=message.chat.id,
        user_id=user.telegram_id,
        group_id=group.telegram_id,
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
