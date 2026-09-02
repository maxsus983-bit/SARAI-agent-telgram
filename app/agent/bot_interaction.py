from __future__ import annotations

import logging

from aiogram.types import Message

from app.agent.loop_guard import loop_guard
from app.config.settings import settings

logger = logging.getLogger("sara.agent.bot_interaction")


def is_bot_message(message: Message) -> bool:
    return bool(
        message.from_user
        and message.from_user.is_bot
    )


def bot_was_explicitly_called(
    message: Message,
    bot_username: str | None,
) -> bool:
    text = message.text or message.caption or ""

    if not text:
        return False

    text_lower = text.lower()

    if bot_username:
        if f"@{bot_username.lower()}" in text_lower:
            return True

    if "sara" in text_lower:
        return True

    return False


class BotInteractionManager:

    def should_process(
        self,
        *,
        message: Message,
        sara_username: str | None = None,
    ) -> bool:

        if not settings.bot_to_bot_mode:
            return False

        if not is_bot_message(message):
            return False

        if not bot_was_explicitly_called(
            message,
            sara_username,
        ):
            return False

        if not loop_guard.can_respond(
            chat_id=message.chat.id,
            is_bot_message=True,
        ):
            logger.warning(
                "Bot-to-bot loop blocked | chat=%s",
                message.chat.id,
            )
            return False

        return True

    def register_incoming_bot(
        self,
        *,
        message: Message,
    ) -> None:
        loop_guard.register_bot_message(
            chat_id=message.chat.id
        )

    def register_response(
        self,
        *,
        chat_id: int,
    ) -> None:
        loop_guard.register_response(
            chat_id=chat_id
        )

    def reset(
        self,
        *,
        chat_id: int,
    ) -> None:
        loop_guard.reset(
            chat_id=chat_id
        )


bot_interaction = BotInteractionManager()
