from __future__ import annotations

import logging
from typing import Any

from aiogram.types import Message

from app.agent.orchestrator import AgentRunResult, sara_orchestrator


logger = logging.getLogger("sara.agent.handler_adapter")


async def process_message(
    message: Message,
    *,
    text: str | None = None,
    is_group: bool = False,
    is_private: bool = False,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = False,
    extra_flags: dict[str, Any] | None = None,
) -> AgentRunResult:

    """
    Telegram Message -> SARA Agent pipeline.

    Oqim:

        Telegram Message
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

    if message is None:
        return AgentRunResult(
            success=False,
            should_send=False,
            error="message_missing",
        )

    user = message.from_user

    if user is None:
        return AgentRunResult(
            success=False,
            should_send=False,
            error="user_missing",
        )

    chat = message.chat

    chat_id = int(chat.id)
    user_id = int(user.id)

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
        return AgentRunResult(
            success=False,
            should_send=False,
            error="empty_message",
        )

    group_id: int | None = None

    if is_group or chat.type in {
        "group",
        "supergroup",
    }:
        group_id = chat_id

    flags: dict[str, Any] = {
        "is_group": is_group,
        "is_private": is_private,
        "sara_called": sara_called,
        "is_reply_to_sara": is_reply_to_sara,
        "proactive_allowed": proactive_allowed,
    }

    if extra_flags:
        flags.update(extra_flags)

    # Telegram message ID'ni doimo agentga beramiz.
    flags.setdefault(
        "source_message_id",
        message.message_id,
    )

    flags.setdefault(
        "telegram_message_id",
        message.message_id,
    )

    flags.setdefault(
        "chat_type",
        chat.type,
    )

    try:
        result = await sara_orchestrator.process(
            chat_id=chat_id,
            user_id=user_id,
            group_id=group_id,
            user_text=actual_text,
            is_group=is_group,
            is_private=is_private,
            sara_called=sara_called,
            is_reply_to_sara=is_reply_to_sara,
            extra_flags=flags,
        )

        if result is None:
            return AgentRunResult(
                success=False,
                should_send=False,
                error="orchestrator_returned_none",
            )

        return result

    except Exception as exc:
        logger.exception(
            "Agent message processing failed | "
            "chat=%s user=%s",
            chat_id,
            user_id,
        )

        return AgentRunResult(
            success=False,
            should_send=False,
            error=str(exc),
            metadata={
                "chat_id": chat_id,
                "user_id": user_id,
                "group_id": group_id,
            },
        )


async def process_private_message(
    message: Message,
    *,
    text: str | None = None,
    sara_called: bool = True,
    is_reply_to_sara: bool = False,
    extra_flags: dict[str, Any] | None = None,
) -> AgentRunResult:

    return await process_message(
        message,
        text=text,
        is_private=True,
        is_group=False,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=False,
        extra_flags=extra_flags,
    )


async def process_group_message(
    message: Message,
    *,
    text: str | None = None,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = True,
    activity_context: dict[str, Any] | None = None,
) -> AgentRunResult:

    return await process_message(
        message,
        text=text,
        is_group=True,
        is_private=False,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=proactive_allowed,
        extra_flags=activity_context,
    )


def result_text(
    result: AgentRunResult | None,
) -> str:

    if result is None:
        return ""

    text = getattr(
        result,
        "response_text",
        "",
    )

    if text:
        return str(text).strip()

    execution = getattr(
        result,
        "execution",
        None,
    )

    if execution is not None:
        text = getattr(
            execution,
            "response_text",
            "",
        )

        if text:
            return str(text).strip()

    return ""


def should_send(
    result: AgentRunResult | None,
) -> bool:

    if result is None:
        return False

    if not getattr(
        result,
        "success",
        False,
    ):
        return False

    explicit = getattr(
        result,
        "should_send",
        None,
    )

    if explicit is False:
        return False

    return bool(
        result_text(result)
    )


def succeeded(
    result: AgentRunResult | None,
) -> bool:

    return bool(
        result
        and getattr(
            result,
            "success",
            False,
        )
    )


__all__ = [
    "process_message",
    "process_private_message",
    "process_group_message",
    "result_text",
    "should_send",
    "succeeded",
        ]
