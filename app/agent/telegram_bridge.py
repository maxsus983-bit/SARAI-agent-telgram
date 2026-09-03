from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot
from aiogram.types import Message

from app.agent.message_processor import (
    ProcessedTelegramMessage,
    process_group_telegram_message,
    process_private_telegram_message,
)


logger = logging.getLogger("sara.agent.telegram_bridge")


# ============================================================
# TEXT HELPERS
# ============================================================

def _message_text(message: Message) -> str:
    """
    Telegram message'dan oddiy text yoki caption oladi.
    """
    return (
        message.text
        or message.caption
        or ""
    ).strip()


def _is_question(text: str) -> bool:
    """
    Xabar savolga o'xshashligini taxmin qiladi.
    Bu qat'iy AI qarori emas — faqat context.
    """

    text = str(text or "").strip()

    if not text:
        return False

    question_words = (
        "nima",
        "nega",
        "qanday",
        "qachon",
        "qayer",
        "kim",
        "qancha",
        "qaysi",
        "bo'ladimi",
        "boladimi",
        "mumkinmi",
        "ayt",
        "tushuntir",
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "can you",
        "можно",
        "почему",
        "как",
        "когда",
        "где",
        "кто",
    )

    lowered = text.lower()

    if "?" in text:
        return True

    return lowered.startswith(
        question_words
    ) or any(
        lowered.startswith(
            word + " "
        )
        for word in question_words
    )


# ============================================================
# SARA MENTION DETECTION
# ============================================================

def _contains_sara_name(
    text: str,
    names: tuple[str, ...] = (
        "sara",
        "sara ai",
        "@sara",
    ),
) -> bool:

    lowered = str(
        text or ""
    ).lower()

    return any(
        name in lowered
        for name in names
    )


def _is_reply_to_sara(
    message: Message,
    bot_user_id: int | None = None,
) -> bool:

    reply = message.reply_to_message

    if reply is None:
        return False

    # Agar javob berilgan message SARA tomonidan yuborilgan bo'lsa.
    if reply.from_user is not None:
        if reply.from_user.is_bot:
            if (
                bot_user_id is None
                or reply.from_user.id == bot_user_id
            ):
                return True

    # Fallback:
    # Telegram ba'zi holatlarda sender ma'lumotini cheklashi mumkin.
    return False


async def detect_sara_reply(
    bot: Bot,
    message: Message,
) -> bool:

    try:
        me = await bot.get_me()

        return _is_reply_to_sara(
            message,
            bot_user_id=me.id,
        )

    except Exception:
        logger.exception(
            "Failed to detect reply to SARA."
        )
        return False


# ============================================================
# PRIVATE MESSAGE BRIDGE
# ============================================================

async def process_private_message(
    message: Message,
    *,
    sara_called: bool = True,
    is_reply_to_sara: bool = False,
    text: str | None = None,
    extra_flags: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:

    actual_text = (
        text
        if text is not None
        else _message_text(message)
    )

    if not actual_text:
        return ProcessedTelegramMessage(
            success=False,
            should_send=False,
            error="empty_message",
        )

    flags: dict[str, Any] = {
        "source": "telegram_private",
        "is_question": _is_question(
            actual_text
        ),
        "sara_called": sara_called,
        "is_reply_to_sara": is_reply_to_sara,
        "allow_user_memory": True,
        "allow_conversation_memory": True,
        "remember_context": True,
        "memory_scope": (
            "user_and_conversation"
        ),
    }

    if extra_flags:
        flags.update(extra_flags)

    return await process_private_telegram_message(
        message,
        text=actual_text,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        extra_flags=flags,
    )


# ============================================================
# GROUP MESSAGE BRIDGE
# ============================================================

async def process_group_message(
    message: Message,
    *,
    sara_called: bool = False,
    is_reply_to_sara: bool = False,
    proactive_allowed: bool = True,
    text: str | None = None,
    activity_context: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:

    actual_text = (
        text
        if text is not None
        else _message_text(message)
    )

    if not actual_text:
        return ProcessedTelegramMessage(
            success=False,
            should_send=False,
            error="empty_message",
        )

    flags: dict[str, Any] = {
        "source": "telegram_group",
        "is_question": _is_question(
            actual_text
        ),
        "sara_called": sara_called,
        "is_reply_to_sara": is_reply_to_sara,
        "proactive_allowed": proactive_allowed,

        # SARA group memory policy:
        "allow_user_memory": True,
        "allow_group_memory": True,
        "allow_conversation_memory": True,
        "remember_context": True,
        "memory_scope": (
            "user_and_group_and_conversation"
        ),
    }

    if activity_context:
        flags.update(
            activity_context
        )

    return await process_group_telegram_message(
        message,
        text=actual_text,
        sara_called=sara_called,
        is_reply_to_sara=is_reply_to_sara,
        proactive_allowed=proactive_allowed,
        activity_context=flags,
    )


# ============================================================
# HIGH LEVEL TELEGRAM PROCESSOR
# ============================================================

async def process_telegram_message(
    message: Message,
    *,
    bot: Bot | None = None,
    is_group: bool = False,
    sara_called: bool = False,
    is_reply_to_sara: bool | None = None,
    proactive_allowed: bool = False,
    text: str | None = None,
    extra_flags: dict[str, Any] | None = None,
) -> ProcessedTelegramMessage:

    """
    Private yoki Group message uchun yagona bridge.

    Agar is_reply_to_sara berilmagan bo'lsa,
    bot orqali avtomatik tekshiradi.
    """

    actual_text = (
        text
        if text is not None
        else _message_text(message)
    )

    if not actual_text:
        return ProcessedTelegramMessage(
            success=False,
            should_send=False,
            error="empty_message",
        )

    if is_reply_to_sara is None:
        if bot is not None:
            is_reply_to_sara = (
                await detect_sara_reply(
                    bot,
                    message,
                )
            )
        else:
            is_reply_to_sara = (
                _is_reply_to_sara(
                    message
                )
            )

    if is_group:
        return await process_group_message(
            message,
            sara_called=sara_called,
            is_reply_to_sara=bool(
                is_reply_to_sara
            ),
            proactive_allowed=proactive_allowed,
            text=actual_text,
            activity_context=extra_flags,
        )

    return await process_private_message(
        message,
        sara_called=True,
        is_reply_to_sara=bool(
            is_reply_to_sara
        ),
        text=actual_text,
        extra_flags=extra_flags,
    )


# ============================================================
# RESPONSE HELPERS
# ============================================================

def get_response_text(
    result: ProcessedTelegramMessage | None,
) -> str:

    if result is None:
        return ""

    return str(
        result.response_text or ""
    ).strip()


def can_send_response(
    result: ProcessedTelegramMessage | None,
) -> bool:

    if result is None:
        return False

    if not result.success:
        return False

    if not result.should_send:
        return False

    return bool(
        get_response_text(result)
    )


def get_error(
    result: ProcessedTelegramMessage | None,
) -> str | None:

    if result is None:
        return "result_missing"

    return result.error


__all__ = [
    "process_private_message",
    "process_group_message",
    "process_telegram_message",
    "detect_sara_reply",
    "get_response_text",
    "can_send_response",
    "get_error",
    ]
