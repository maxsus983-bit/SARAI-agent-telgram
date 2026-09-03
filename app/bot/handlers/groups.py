from __future__ import annotations

import logging
import time
from typing import Any

from aiogram import Bot, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.agent.telegram_bridge import process_group_message
from app.services.message_service import message_service
from app.services.user_service import user_service

logger = logging.getLogger("sara.bot.groups")

router = Router(name="groups")


# ============================================================
# SARA GROUP SETTINGS
# ============================================================

BOT_TO_BOT_ENABLED = True

# Bir bot zanjirining maksimal uzunligi.
# SARA -> BotA -> SARA -> BotA ...
# kabi cheksiz loop bo'lishining oldini oladi.
MAX_BOT_CHAIN = 5

# Bir xil botga juda tez-tez javob berishdan himoya.
BOT_COOLDOWN_SECONDS = 30.0


# ============================================================
# RUNTIME STATE
# ============================================================

_last_bot_response: dict[tuple[int, int], float] = {}


# ============================================================
# TEXT
# ============================================================

def _get_text(message: Message) -> str:
    return (
        message.text
        or message.caption
        or ""
    ).strip()


# ============================================================
# SARA ID
# ============================================================

async def _get_sara_id(bot: Bot) -> int:
    me = await bot.get_me()
    return int(me.id)


# ============================================================
# MENTION CHECK
# ============================================================

def _contains_sara_mention(
    message: Message,
    sara_username: str | None,
) -> bool:

    text = _get_text(message).lower()

    if not text:
        return False

    # Oddiy chaqirishlar
    direct_words = (
        "sara",
        "sára",
        "сара",
    )

    for word in direct_words:
        if word in text:
            return True

    # @username
    if sara_username:
        username = sara_username.lower().lstrip("@")

        if username and f"@{username}" in text:
            return True

    # Telegram entities
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                try:
                    value = text[
                        entity.offset:
                        entity.offset + entity.length
                    ]

                    if sara_username:
                        if (
                            value.lstrip("@").lower()
                            == sara_username.lower().lstrip("@")
                        ):
                            return True

                except Exception:
                    continue

    return False


# ============================================================
# REPLY TO SARA
# ============================================================

async def _is_reply_to_sara(
    bot: Bot,
    message: Message,
) -> bool:

    reply = message.reply_to_message

    if reply is None:
        return False

    if reply.from_user is None:
        return False

    try:
        sara_id = await _get_sara_id(bot)

        return (
            int(reply.from_user.id)
            == sara_id
        )

    except Exception:
        logger.exception(
            "SARA reply tekshirishda xato."
        )

        return False


# ============================================================
# REPLY TO OTHER BOT
# ============================================================

def _is_reply_to_bot(
    message: Message,
) -> bool:

    reply = message.reply_to_message

    if reply is None:
        return False

    if reply.from_user is None:
        return False

    return bool(
        reply.from_user.is_bot
    )


# ============================================================
# BOT MESSAGE
# ============================================================

def _is_bot_message(
    message: Message,
) -> bool:

    if message.from_user is None:
        return False

    return bool(
        message.from_user.is_bot
    )


# ============================================================
# BOT CHAIN
# ============================================================

def _get_bot_chain_depth(
    message: Message,
) -> int:

    depth = 0

    current = message.reply_to_message

    visited: set[int] = set()

    while current is not None:

        if current.from_user is not None:

            user_id = int(
                current.from_user.id
            )

            if user_id in visited:
                break

            visited.add(user_id)

            if current.from_user.is_bot:
                depth += 1

        current = current.reply_to_message

        if depth >= MAX_BOT_CHAIN:
            break

    return depth


# ============================================================
# BOT COOLDOWN
# ============================================================

def _bot_cooldown_allowed(
    chat_id: int,
    bot_id: int,
) -> bool:

    key = (
        int(chat_id),
        int(bot_id),
    )

    now = time.monotonic()

    previous = _last_bot_response.get(
        key,
        0.0,
    )

    if (
        now - previous
        < BOT_COOLDOWN_SECONDS
    ):
        return False

    _last_bot_response[key] = now

    return True


# ============================================================
# CLEAN MEMORY
# ============================================================

def _cleanup_cooldowns() -> None:

    if len(_last_bot_response) < 5000:
        return

    now = time.monotonic()

    expired = [
        key
        for key, value
        in _last_bot_response.items()
        if now - value
        > BOT_COOLDOWN_SECONDS * 10
    ]

    for key in expired:
        _last_bot_response.pop(
            key,
            None,
        )


# ============================================================
# GROUP HANDLER
# ============================================================

@router.message()
async def group_message_handler(
    message: Message,
    bot: Bot,
) -> None:

    # --------------------------------------------------------
    # Faqat guruhlar
    # --------------------------------------------------------

    if message.chat.type not in {
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    }:
        return

    # --------------------------------------------------------
    # User
    # --------------------------------------------------------

    if message.from_user is None:
        return

    text = _get_text(message)

    if not text:
        return

    chat_id = int(
        message.chat.id
    )

    sender_id = int(
        message.from_user.id
    )

    sender_is_bot = bool(
        message.from_user.is_bot
    )

    # --------------------------------------------------------
    # SARA
    # --------------------------------------------------------

    try:
        sara = await bot.get_me()

        sara_id = int(
            sara.id
        )

        sara_username = (
            sara.username
            or ""
        )

    except Exception:
        logger.exception(
            "SARA bot ma'lumotini olishda xato."
        )
        return

    # --------------------------------------------------------
    # SARA o'z xabarini qayta ishlamasin
    # --------------------------------------------------------

    if sender_id == sara_id:
        return

    # --------------------------------------------------------
    # BOT TO BOT
    # --------------------------------------------------------

    if sender_is_bot:

        if not BOT_TO_BOT_ENABLED:
            return

        # SARA ga reply/mention qilmagan oddiy bot xabari
        # avtomatik ravishda javobga sabab bo'lmaydi.
        bot_mentions_sara = (
            _contains_sara_mention(
                message,
                sara_username,
            )
        )

        bot_replied_to_sara = (
            await _is_reply_to_sara(
                bot,
                message,
            )
        )

        # Boshqa botga javob berayotgan bo'lsa
        # va SARA chaqirilmagan bo'lsa:
        if (
            not bot_mentions_sara
            and not bot_replied_to_sara
        ):
            return

        # Loop protection
        chain_depth = _get_bot_chain_depth(
            message
        )

        if chain_depth >= MAX_BOT_CHAIN:
            logger.warning(
                "Bot chain limit | chat=%s | depth=%s",
                chat_id,
                chain_depth,
            )
            return

        # Cooldown
        if not _bot_cooldown_allowed(
            chat_id,
            sender_id,
        ):
            logger.info(
                "Bot cooldown | chat=%s | bot=%s",
                chat_id,
                sender_id,
            )
            return

    # --------------------------------------------------------
    # USER MESSAGE
    # --------------------------------------------------------

    try:

        await user_service.get_or_create_user(
            telegram_id=sender_id,
            username=(
                message.from_user.username
            ),
            first_name=(
                message.from_user.first_name
            ),
            last_name=(
                message.from_user.last_name
            ),
            language_code=(
                message.from_user.language_code
            ),
            is_bot=sender_is_bot,
        )

    except Exception:
        logger.exception(
            "Group user DB update failed | "
            "chat=%s user=%s",
            chat_id,
            sender_id,
        )

    # --------------------------------------------------------
    # SAVE MESSAGE
    # --------------------------------------------------------

    try:

        await message_service.save_message(
            telegram_message_id=(
                message.message_id
            ),
            chat_id=chat_id,
            user_telegram_id=sender_id,
            role=(
                "assistant"
                if sender_is_bot
                else "user"
            ),
            content=text,
            message_type="text",
            reply_to_message_id=(
                message.reply_to_message.message_id
                if message.reply_to_message
                else None
            ),
            is_bot_message=sender_is_bot,
        )

    except Exception:
        logger.exception(
            "Group message save failed | "
            "chat=%s user=%s",
            chat_id,
            sender_id,
        )

    # --------------------------------------------------------
    # SARA CHAQIRILGANMI?
    # --------------------------------------------------------

    sara_mentioned = (
        _contains_sara_mention(
            message,
            sara_username,
        )
    )

    reply_to_sara = (
        await _is_reply_to_sara(
            bot,
            message,
        )
    )

    reply_to_other_bot = (
        _is_reply_to_bot(
            message
        )
    )

    # --------------------------------------------------------
    # GROUP AGENT
    # --------------------------------------------------------

    try:

        result = await process_group_message(
            message,
            text=text,

            sara_called=(
                sara_mentioned
                or reply_to_sara
            ),

            is_reply_to_sara=(
                reply_to_sara
            ),

            extra_flags={

                "source": "group_handler",

                "source_message_id":
                    message.message_id,

                "chat_id":
                    chat_id,

                "user_id":
                    sender_id,

                "is_group":
                    True,

                "is_private":
                    False,

                "is_bot":
                    sender_is_bot,

                "bot_to_bot":
                    sender_is_bot,

                "bot_chain_depth":
                    _get_bot_chain_depth(
                        message
                    ),

                "reply_to_other_bot":
                    reply_to_other_bot,

                "allow_user_memory":
                    not sender_is_bot,

                "allow_group_memory":
                    True,

                "allow_conversation_memory":
                    True,

                "remember_context":
                    True,

                "memory_scope":
                    "user_group_conversation",

                "sara_username":
                    sara_username,

            },
        )

    except Exception:
        logger.exception(
            "SARA group Agent failed | "
            "chat=%s user=%s",
            chat_id,
            sender_id,
        )
        return

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    if not result:
        return

    if not getattr(
        result,
        "success",
        False,
    ):

        logger.warning(
            "Group Agent failure | "
            "chat=%s user=%s error=%s",
            chat_id,
            sender_id,
            getattr(
                result,
                "error",
                None,
            ),
        )

        return

    if not getattr(
        result,
        "should_send",
        False,
    ):
        return

    response_text = (
        getattr(
            result,
            "response_text",
            "",
        )
        or ""
    ).strip()

    if not response_text:
        return

    # --------------------------------------------------------
    # DUPLICATE SEND PROTECTION
    # --------------------------------------------------------

    execution = getattr(
        result,
        "agent_result",
        None,
    )

    execution_result = getattr(
        execution,
        "execution",
        None,
    )

    already_sent = False

    if execution_result is not None:

        metadata = getattr(
            execution_result,
            "metadata",
            {},
        )

        if isinstance(
            metadata,
            dict,
        ):
            already_sent = bool(
                metadata.get(
                    "telegram_sent",
                    False,
                )
            )

    if already_sent:
        return

    # --------------------------------------------------------
    # SEND TO GROUP
    # --------------------------------------------------------

    try:

        sent = await bot.send_message(
            chat_id=chat_id,
            text=response_text,

            # SARA guruhda javob berayotgan
            # xabariga reply qiladi.
            reply_to_message_id=(
                message.message_id
            ),
        )

    except Exception:

        logger.exception(
            "Could not send SARA group response | "
            "chat=%s",
            chat_id,
        )

        return

    # --------------------------------------------------------
    # SAVE SARA RESPONSE
    # --------------------------------------------------------

    try:

        await message_service.save_message(
            telegram_message_id=(
                sent.message_id
            ),
            chat_id=chat_id,

            # Guruhdagi SARA javobining
            # egasi SARA emas, source user/bot.
            user_telegram_id=sara_id,

            role="assistant",

            content=response_text,

            message_type="text",

            reply_to_message_id=(
                message.message_id
            ),

            is_bot_message=True,
        )

    except Exception:

        logger.exception(
            "Could not save SARA group response | "
            "chat=%s",
            chat_id,
        )

    _cleanup_cooldowns()

    logger.info(
        "SARA group response sent | "
        "chat=%s | source=%s | bot=%s",
        chat_id,
        sender_id,
        sender_is_bot,
    )


__all__ = [
    "router",
    ]
