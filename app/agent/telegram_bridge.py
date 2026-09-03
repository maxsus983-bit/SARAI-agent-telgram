from __future__ import annotations

import logging
from typing import Any

from aiogram.types import Message

from app.agent.message_processor import (
    ProcessedTelegramMessage,
    telegram_agent_processor,
)

logger = logging.getLogger("sara.agent.telegram_bridge")


async def process_private_message(
    message: Message,
    *,
    sara_called: bool = True,
    is_reply_to_sara: bool = False,
    extra_flags: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:
    """
    Private Telegram chat uchun Agent bridge.
    """

    return await telegram_agent_processor.process(
        message,
        is_group=False,
        is_private=True,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        is_question=_is_question(
            message.text or message.caption or ""
        ),
        proactive_allowed=False,
        extra_flags=extra_flags,
    )


async def process_group_message(
    message: Message,
    *,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = True,
    extra_flags: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:
    """
    Group/supergroup Telegram chat uchun Agent bridge.

    SARA chaqirilmagan bo'lsa ham proactive_allowed=True
    bo'lsa, Brain/Proactive tizimi o'zi qaror qilishi mumkin.
    """

    return await telegram_agent_processor.process(
        message,
        is_group=True,
        is_private=False,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        is_question=_is_question(
            message.text or message.caption or ""
        ),
        proactive_allowed=proactive_allowed,
        extra_flags=extra_flags,
    )


def _is_question(text: str) -> bool:
    """
    Oddiy question detector.

    Brain bundan kuchliroq qaror chiqaradi;
    bu faqat boshlang'ich signal.
    """

    text = text.strip()

    if not text:
        return False

    if "?" in text:
        return True

    lowered = text.lower()

    question_words = (
        "kim",
        "nima",
        "nega",
        "qanday",
        "qachon",
        "qayer",
        "qaysi",
        "menga",
        "aytchi",
        "bilasanmi",
        "можешь",
        "почему",
        "как",
        "когда",
        "где",
        "что",
        "why",
        "how",
        "when",
        "where",
        "what",
    )

    first_word = lowered.split()[0] if lowered.split() else ""

    return first_word in question_words
