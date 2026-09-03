from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from aiogram.types import Message

from app.agent.handler_adapter import process_message

logger = logging.getLogger("sara.agent.message_processor")


@dataclass
class ProcessedTelegramMessage:
    success: bool
    should_send: bool
    response_text: str = ""
    error: str | None = None
    agent_result: Any | None = None


class TelegramAgentProcessor:
    """
    Telegram Message -> SARA Agent bridge.

    Bu qatlam Telegram Message obyektidan kerakli
    ma'lumotlarni olib, Agent tizimiga uzatadi.

    Oqim:

        Telegram Message
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
        is_question: bool = False,
        proactive_allowed: bool = True,
        extra_flags: dict[str, Any] | None = None,
    ) -> ProcessedTelegramMessage:

        try:
            chat = message.chat
            user = message.from_user

            if user is None:
                return ProcessedTelegramMessage(
                    success=False,
                    should_send=False,
                    error="message_from_user_missing",
                )

            text = message.text or message.caption or ""

            text = text.strip()

            if not text:
                return ProcessedTelegramMessage(
                    success=True,
                    should_send=False,
                    error="empty_text",
                )

            group_id: int | None = None

            if is_group:
                group_id = chat.id

            reply_to_message_id: int | None = None

            if message.reply_to_message:
                reply_to_message_id = (
                    message.reply_to_message.message_id
                )

            result = await process_message(
                chat_id=chat.id,
                user_id=user.id,
                user_text=text,
                group_id=group_id,
                reply_to_message_id=reply_to_message_id,
                message_id=message.message_id,
                is_group=is_group,
                is_private=is_private,
                is_bot_message=bool(user.is_bot),
                sara_called=sara_called,
                is_reply_to_sara=is_reply_to_sara,
                is_question=is_question,
                proactive_allowed=proactive_allowed,
                extra_flags=extra_flags,
            )

            return ProcessedTelegramMessage(
                success=result.success,
                should_send=result.should_send,
                response_text=result.response_text,
                error=result.error,
                agent_result=result,
            )

        except Exception as exc:
            logger.exception(
                "Telegram Agent Processor failed | "
                "chat=%s",
                message.chat.id,
            )

            return ProcessedTelegramMessage(
                success=False,
                should_send=False,
                error=str(exc),
            )


telegram_agent_processor = TelegramAgentProcessor() 
