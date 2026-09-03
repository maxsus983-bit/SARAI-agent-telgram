from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from app.agent.telegram_bridge import process_private_message
from app.services.message_service import message_service
from app.services.user_service import user_service


logger = logging.getLogger("sara.bot.private")

router = Router(name="private")


# ============================================================
# HELPERS
# ============================================================

def _get_text(message: Message) -> str:
    """
    Telegram xabaridan text yoki caption oladi.
    """
    return (
        message.text
        or message.caption
        or ""
    ).strip()


async def _is_reply_to_sara(
    bot: Bot,
    message: Message,
) -> bool:
    """
    Xabar SARA'ning oldingi xabariga reply ekanini tekshiradi.
    """

    reply = message.reply_to_message

    if reply is None:
        return False

    if reply.from_user is None:
        return False

    if not reply.from_user.is_bot:
        return False

    try:
        me = await bot.get_me()

        return reply.from_user.id == me.id

    except Exception:
        logger.exception(
            "Could not check SARA reply."
        )
        return False


# ============================================================
# PRIVATE MESSAGE HANDLER
# ============================================================

@router.message(F.chat.type == ChatType.PRIVATE)
async def private_message_handler(
    message: Message,
    bot: Bot,
) -> None:
    """
    Faqat PRIVATE chat xabarlarini qayta ishlaydi.

    Muhim:
        Group/supergroup xabarlari bu handlerga tushmaydi.
        Ular groups.py tomonidan ishlanadi.
    """

    if message.from_user is None:
        return

    text = _get_text(message)

    if not text:
        return

    user_id = int(message.from_user.id)
    chat_id = int(message.chat.id)

    # ========================================================
    # USER UPSERT
    # ========================================================

    try:
        await user_service.get_or_create_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code,
            is_bot=message.from_user.is_bot,
        )

    except Exception:
        logger.exception(
            "Could not update user | user=%s",
            user_id,
        )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

    try:
        await message_service.save_message(
            telegram_message_id=message.message_id,
            chat_id=chat_id,
            user_telegram_id=user_id,
            role="user",
            content=text,
            message_type="text",
            reply_to_message_id=(
                message.reply_to_message.message_id
                if message.reply_to_message
                else None
            ),
            is_bot_message=False,
        )

    except Exception:
        logger.exception(
            "Could not save private message | "
            "chat=%s user=%s",
            chat_id,
            user_id,
        )

    # ========================================================
    # REPLY DETECTION
    # ========================================================

    reply_to_sara = await _is_reply_to_sara(
        bot,
        message,
    )

    # Private chatda foydalanuvchi SARA bilan gaplashmoqda.
    sara_called = True

    # ========================================================
    # AGENT
    # ========================================================

    try:
        result = await process_private_message(
            message,
            text=text,
            sara_called=sara_called,
            is_reply_to_sara=reply_to_sara,
            extra_flags={
                # ------------------------------------------------
                # SOURCE
                # ------------------------------------------------
                "source": "private_handler",
                "source_message_id": message.message_id,
                "telegram_message_id": message.message_id,

                # ------------------------------------------------
                # CHAT
                # ------------------------------------------------
                "chat_id": chat_id,
                "user_id": user_id,
                "chat_type": message.chat.type,
                "is_private": True,
                "is_group": False,

                # ------------------------------------------------
                # MEMORY
                # ------------------------------------------------
                "allow_user_memory": True,
                "allow_conversation_memory": True,
                "remember_context": True,
                "memory_scope": "user_and_conversation",

                # ------------------------------------------------
                # TOOLS
                # ------------------------------------------------
                "allow_telegram_tools": True,
                "allow_reminders": True,
                "allow_memory_tools": True,
                "allow_media_tools": True,
                "allow_bot_interaction": True,

                # ------------------------------------------------
                # AGENT
                # ------------------------------------------------
                "is_bot": bool(
                    message.from_user.is_bot
                ),
                "is_bot_message": bool(
                    message.from_user.is_bot
                ),
                "sara_called": sara_called,
                "is_reply_to_sara": reply_to_sara,

                # ------------------------------------------------
                # QUESTION
                # ------------------------------------------------
                "is_question": (
                    "?" in text
                ),
            },
        )

    except Exception:
        logger.exception(
            "SARA private Agent failed | "
            "chat=%s user=%s",
            chat_id,
            user_id,
        )
        return

    # ========================================================
    # RESULT VALIDATION
    # ========================================================

    if result is None:
        return

    if not result.success:
        logger.warning(
            "Private Agent returned failure | "
            "chat=%s user=%s error=%s",
            chat_id,
            user_id,
            result.error,
        )
        return

    if not result.should_send:
        return

    response_text = (
        result.response_text
        or ""
    ).strip()

    if not response_text:
        return

    # ========================================================
    # CHECK WHETHER EXECUTOR ALREADY SENT MESSAGE
    # ========================================================

    execution = getattr(
        result,
        "execution",
        None,
    )

    already_sent = False

    if execution is not None:
        metadata = getattr(
            execution,
            "metadata",
            {},
        )

        if isinstance(metadata, dict):
            already_sent = bool(
                metadata.get(
                    "telegram_sent",
                    False,
                )
            )

    if already_sent:
        logger.debug(
            "Private response already sent by executor | "
            "chat=%s user=%s",
            chat_id,
            user_id,
        )
        return

    # ========================================================
    # FALLBACK SEND
    # ========================================================

    try:
        sent = await bot.send_message(
            chat_id=chat_id,
            text=response_text,
            reply_to_message_id=message.message_id,
        )

    except Exception:
        logger.exception(
            "Could not send private SARA response | "
            "chat=%s",
            chat_id,
        )
        return

    # ========================================================
    # SAVE SARA RESPONSE
    # ========================================================

    try:
        await message_service.save_message(
            telegram_message_id=sent.message_id,
            chat_id=chat_id,
            user_telegram_id=user_id,
            role="assistant",
            content=response_text,
            message_type="text",
            reply_to_message_id=message.message_id,
            is_bot_message=True,
        )

    except Exception:
        logger.exception(
            "Could not save SARA private response | "
            "chat=%s user=%s",
            chat_id,
            user_id,
        )

    logger.info(
        "SARA private response sent | "
        "chat=%s user=%s message=%s",
        chat_id,
        user_id,
        sent.message_id,
    )


# ============================================================
# EXPORT
# ============================================================

__all__ = [
    "router",
    ]
