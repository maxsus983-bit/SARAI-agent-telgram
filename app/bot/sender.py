from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest


async def send_answer(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
) -> None:

    if not text:
        return

    # Telegram maksimal xabar uzunligi.
    max_length = 4096

    chunks = [
        text[i:i + max_length]
        for i in range(0, len(text), max_length)
    ]

    for index, chunk in enumerate(chunks):

        reply_id = (
            reply_to_message_id
            if index == 0
            else None
        )

        try:

            await bot.send_chat_action(
                chat_id=chat_id,
                action=ChatAction.TYPING,
            )

        except TelegramBadRequest:
            pass

        await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            reply_to_message_id=reply_id,
        )
