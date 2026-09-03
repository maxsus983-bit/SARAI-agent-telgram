from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aiogram.types import Message

from app.agent.handler_adapter import (
    process_message,
    result_text,
    should_send,
)


logger = logging.getLogger("sara.agent.message_processor")


@dataclass
class ProcessedTelegramMessage:
    success: bool
    should_send: bool = False
    response_text: str = ""
    error: str | None = None
    agent_result: Any | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.response_text = str(
            self.response_text or ""
        ).strip()

    @property
    def succeeded(self) -> bool:
        return self.success

    @property
    def has_response(self) -> bool:
        return bool(self.response_text)

    @property
    def decision(self) -> Any | None:
        """
        Orchestrator natijasidagi Brain decision'ni
        handlerlarga qulay qilib chiqaradi.
        """
        if self.agent_result is None:
            return None

        return getattr(
            self.agent_result,
            "decision",
            None,
        )

    @property
    def plan(self) -> Any | None:
        if self.agent_result is None:
            return None

        return getattr(
            self.agent_result,
            "plan",
            None,
        )

    @property
    def execution(self) -> Any | None:
        if self.agent_result is None:
            return None

        return getattr(
            self.agent_result,
            "execution",
            None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "should_send": self.should_send,
            "response_text": self.response_text,
            "error": self.error,
            "metadata": self.metadata,
        }


class TelegramMessageProcessor:
    """
    Telegram xabarlarini SARA Agent pipeline'iga uzatadi.

    Oqim:

        Telegram
           ↓
        MessageProcessor
           ↓
        Handler Adapter
           ↓
        Orchestrator
           ↓
        Brain
           ↓
        Planner
           ↓
        Executor
    """

    async def process(
        self,
        message: Message,
        *,
        is_group: bool = False,
        is_private: bool = False,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        proactive_allowed: bool = False,
        text: str | None = None,
        extra_flags: dict[str, Any] | None = None,
    ) -> ProcessedTelegramMessage:

        if message is None:
            return ProcessedTelegramMessage(
                success=False,
                error="message_missing",
            )

        if message.from_user is None:
            return ProcessedTelegramMessage(
                success=False,
                error="user_missing",
            )

        actual_text = (
            text
            if text is not None
            else (
                message.text
                or message.caption
                or ""
            )
        ).strip()

        if not actual_text:
            return ProcessedTelegramMessage(
                success=False,
                error="empty_message",
            )

        chat_id = int(message.chat.id)
        user_id = int(message.from_user.id)

        flags: dict[str, Any] = {
            "source": "telegram",
            "source_message_id": message.message_id,
            "telegram_message_id": message.message_id,
            "chat_id": chat_id,
            "user_id": user_id,
            "chat_type": message.chat.type,
            "is_group": is_group,
            "is_private": is_private,
        }

        if extra_flags:
            flags.update(extra_flags)

        try:
            agent_result = await process_message(
                message,
                text=actual_text,
                is_group=is_group,
                is_private=is_private,
                sara_called=sara_called,
                is_reply_to_sara=is_reply_to_sara,
                proactive_allowed=proactive_allowed,
                extra_flags=flags,
            )

            if agent_result is None:
                return ProcessedTelegramMessage(
                    success=False,
                    error="agent_result_missing",
                    metadata={
                        "chat_id": chat_id,
                        "user_id": user_id,
                    },
                )

            response = result_text(
                agent_result
            )

            send_allowed = should_send(
                agent_result
            )

            agent_error = getattr(
                agent_result,
                "error",
                None,
            )

            agent_metadata = getattr(
                agent_result,
                "metadata",
                {},
            )

            if not isinstance(
                agent_metadata,
                dict,
            ):
                agent_metadata = {}

            metadata = {
                **agent_metadata,
                "chat_id": chat_id,
                "user_id": user_id,
                "message_id": message.message_id,
                "is_group": is_group,
                "is_private": is_private,
            }

            return ProcessedTelegramMessage(
                success=bool(
                    getattr(
                        agent_result,
                        "success",
                        False,
                    )
                ),
                should_send=send_allowed,
                response_text=response,
                error=agent_error,
                agent_result=agent_result,
                metadata=metadata,
            )

        except Exception as exc:
            logger.exception(
                "Telegram message processing failed | "
                "chat=%s user=%s message=%s",
                chat_id,
                user_id,
                message.message_id,
            )

            return ProcessedTelegramMessage(
                success=False,
                should_send=False,
                error=str(exc),
                metadata={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "message_id": message.message_id,
                },
            )


# ============================================================
# GLOBAL PROCESSOR
# ============================================================

telegram_message_processor = (
    TelegramMessageProcessor()
)


# ============================================================
# COMPATIBILITY FUNCTION
# ============================================================

async def process_telegram_message(
    message: Message,
    *,
    is_group: bool = False,
    is_private: bool = False,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = False,
    text: str | None = None,
    extra_flags: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:

    return await telegram_message_processor.process(
        message,
        is_group=is_group,
        is_private=is_private,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=proactive_allowed,
        text=text,
        extra_flags=extra_flags,
    )


async def process_private_telegram_message(
    message: Message,
    *,
    text: str | None = None,
    sara_called: bool = True,
    is_reply_to_sara: bool = False,
    extra_flags: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:

    return await telegram_message_processor.process(
        message,
        text=text,
        is_private=True,
        is_group=False,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=False,
        extra_flags=extra_flags,
    )


async def process_group_telegram_message(
    message: Message,
    *,
    text: str | None = None,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = True,
    activity_context: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:

    return await telegram_message_processor.process(
        message,
        text=text,
        is_group=True,
        is_private=False,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=proactive_allowed,
        extra_flags=activity_context,
    )


__all__ = [
    "ProcessedTelegramMessage",
    "TelegramMessageProcessor",
    "telegram_message_processor",
    "process_telegram_message",
    "process_private_telegram_message",
    "process_group_telegram_message",
            ]
