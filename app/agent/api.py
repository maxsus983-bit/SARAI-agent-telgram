from __future__ import annotations

import logging
from typing import Any

from aiogram.types import Message

from app.agent.group_agent import group_agent
from app.agent.telegram_bridge import process_private_message

logger = logging.getLogger("sara.agent.api")


async def handle_private(
    message: Message,
    *,
    sara_called: bool = True,
    is_reply_to_sara: bool = False,
    extra_flags: dict[str, Any] | None = None,
):
    """
    SARA private chat uchun yagona Agent API.
    """

    return await process_private_message(
        message,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        extra_flags=extra_flags,
    )


async def handle_group(
    message: Message,
    *,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = True,
    activity_context: dict[str, Any] | None = None,
):
    """
    SARA group chat uchun yagona Agent API.

    proactive_allowed=True bo'lsa,
    SARA chaqirilmagan paytda ham Agent qaror
    chiqarishi mumkin.
    """

    return await group_agent.process(
        message,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=proactive_allowed,
        activity_context=activity_context,
    )


def result_text(result: Any) -> str:
    """
    Agent natijasidan javob matnini xavfsiz olish.
    """

    if result is None:
        return ""

    text = getattr(
        result,
        "response_text",
        "",
    )

    if text is None:
        return ""

    return str(text).strip()


def should_send(result: Any) -> bool:
    """
    Agent natijasi Telegramga yuborilishi kerakmi?
    """

    if result is None:
        return False

    return bool(
        getattr(
            result,
            "should_send",
            False,
        )
    )


def succeeded(result: Any) -> bool:
    """
    Agent muvaffaqiyatli ishladimi?
    """

    if result is None:
        return False

    return bool(
        getattr(
            result,
            "success",
            False,
        )
    )


__all__ = [
    "handle_private",
    "handle_group",
    "result_text",
    "should_send",
    "succeeded",
  ]
