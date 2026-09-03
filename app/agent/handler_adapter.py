from __future__ import annotations

import logging
from typing import Any

from app.agent.orchestrator import (
    AgentRunResult,
    sara_orchestrator,
)

logger = logging.getLogger("sara.agent.handler_adapter")


async def process_message(
    *,
    chat_id: int,
    user_id: int | None,
    user_text: str,
    group_id: int | None = None,
    reply_to_message_id: int | None = None,
    message_id: int | None = None,
    is_group: bool = False,
    is_private: bool = False,
    is_bot_message: bool = False,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    is_question: bool = False,
    proactive_allowed: bool = True,
    extra_flags: dict[str, Any] | None = None,
) -> AgentRunResult:
    """
    Telegram handlerlar uchun SARA Agent adapteri.

    Handlerlar Brain/Planner/Executor ichki arxitekturasini
    bilishi shart emas.

    Ular faqat process_message() chaqiradi.
    """

    try:
        result = await sara_orchestrator.process(
            chat_id=chat_id,
            user_id=user_id,
            user_text=user_text,
            group_id=group_id,
            reply_to_message_id=reply_to_message_id,
            message_id=message_id,
            is_group=is_group,
            is_private=is_private,
            is_bot_message=is_bot_message,
            sara_called=sara_called,
            is_reply_to_sara=is_reply_to_sara,
            is_question=is_question,
            proactive_allowed=proactive_allowed,
            extra_flags=extra_flags,
        )

        logger.debug(
            "Agent message processed | "
            "chat=%s | success=%s | send=%s",
            chat_id,
            result.success,
            result.should_send,
        )

        return result

    except Exception as exc:
        logger.exception(
            "Agent adapter failed | chat=%s",
            chat_id,
        )

        return AgentRunResult(
            success=False,
            should_send=False,
            error=str(exc),
        )
