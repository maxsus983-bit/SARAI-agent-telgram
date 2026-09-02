from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import Message

from app.agent.emotional_state import emotional_state
from app.agent.proactive import proactive_agent
from app.bot.middleware.rate_limit import rate_limiter
from app.config.settings import settings


@dataclass
class ChatContext:
    chat_id: int
    user_id: int
    is_private: bool
    is_group: bool
    is_bot: bool
    text: str
    is_question: bool


class ChatContextBuilder:

    def build(
        self,
        message: Message,
    ) -> ChatContext | None:

        if message.from_user is None:
            return None

        text = (
            message.text
            or message.caption
            or ""
        ).strip()

        return ChatContext(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            is_private=(
                message.chat.type == "private"
            ),
            is_group=(
                message.chat.type
                in {"group", "supergroup"}
            ),
            is_bot=bool(
                message.from_user.is_bot
            ),
            text=text,
            is_question=(
                proactive_agent.looks_like_question(
                    text
                )
            ),
        )

    def allow(
        self,
        context: ChatContext,
    ) -> bool:

        if not context.is_group:
            return rate_limiter.allow_user(
                user_id=context.user_id,
                interval=(
                    settings.user_rate_limit_seconds
                ),
            )

        # Guruhda ham user va group limitlari
        # birgalikda ishlaydi.
        if not rate_limiter.allow_user(
            user_id=context.user_id,
            interval=(
                settings.user_rate_limit_seconds
            ),
        ):
            return False

        if not rate_limiter.allow_group(
            chat_id=context.chat_id,
            interval=(
                settings.group_rate_limit_seconds
            ),
        ):
            return False

        return True

    def update_emotional_state(
        self,
        context: ChatContext,
    ) -> None:

        emotional_state.update(
            chat_id=context.chat_id,
            user_id=context.user_id,
            mood=(
                "curious"
                if context.is_question
                else "neutral"
            ),
            intensity_change=(
                0.05
                if context.is_question
                else 0.01
            ),
            curiosity_change=(
                0.08
                if context.is_question
                else 0.01
            ),
        )


chat_context_builder = ChatContextBuilder()
