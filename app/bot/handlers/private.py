from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import Message

from app.agent.telegram_bridge import process_private_message
from app.services.message_service import message_service
from app.services.user_service import user_service

logger = logging.getLogger("sara.bot.private")

router = Router(name="private_messages")


def looks_like_question(text: str) -> bool:
    """
    Xabar savolga o'xshaydimi?
    """

    text = text.strip().lower()

    if not text:
        return False

    if "?" in text:
        return True

    question_words = (
        "nima",
        "nega",
        "qanday",
        "qachon",
        "qayer",
        "qayerda",
        "kim",
        "kimga",
        "kimni",
        "qancha",
        "qaysi",
        "mumkinmi",
        "bilasanmi",
        "ayt",
        "aytchi",
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "which",
        "can you",
        "do you",
        "почему",
        "как",
        "когда",
        "где",
        "кто",
        "какой",
        "можешь",
    )

    return any(
        text == word or text.startswith(word + " ")
        for word in question_words
    )


async def is_reply_to_sara(message: Message) -> bool:
    """
    User SARA yuborgan xabarga reply qilganmi?
    """

    if not message.reply_to_message:
        return False

    replied_user = message.reply_to_message.from_user

    if replied_user is None:
        return False

    if not replied_user.is_bot:
        return False

    try:
        sara = await message.bot.get_me()
    except Exception:
        logger.exception(
            "SARA get_me failed while checking reply."
        )
        return False

    return replied_user.id == sara.id


@router.message(
    lambda message: (
        message.chat.type == "private"
        and bool(message.from_user)
        and bool(message.text)
    )
)
async def handle_private_message(message: Message) -> None:

    if message.from_user is None:
        return

    if not message.text:
        return

    user = message.from_user
    chat_id = message.chat.id
    text = message.text.strip()

    if not text:
        return

    try:

        # ==================================================
        # USER
        # ==================================================

        db_user = await user_service.get_or_create(
            user
        )

        # ==================================================
        # SAVE USER MESSAGE
        # ==================================================

        saved_message = await message_service.save(
            telegram_message_id=message.message_id,
            chat_id=chat_id,
            user_telegram_id=user.id,
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

        # ==================================================
        # MESSAGE FLAGS
        # ==================================================

        question = looks_like_question(text)

        reply_to_sara = await is_reply_to_sara(
            message
        )

        # ==================================================
        # AGENT PIPELINE
        #
        # Telegram
        #      ↓
        # Telegram Bridge
        #      ↓
        # Agent Runtime
        #      ↓
        # Brain
        #      ↓
        # Planner
        #      ↓
        # Executor
        #      ↓
        # Tools / Memory / Reminder
        #      ↓
        # Telegram
        # ==================================================

        result = await process_private_message(
            message=message,
            sara_called=True,
            is_reply_to_sara=reply_to_sara,
            extra_flags={
                "source": "telegram_private",

                "source_message_id": saved_message.id,

                "is_question": question,

                # Private user memory ishlaydi.
                "allow_user_memory": True,

                # Conversation memory ishlaydi.
                "allow_conversation_memory": True,

                # User ma'lumotlarini uzoq muddat
                # eslab qolish uchun signal.
                "remember_context": True,

                # Private chatda to'liq user scope.
                "memory_scope": "user_and_conversation",
            },
        )

        # ==================================================
        # AGENT RESULT
        # ==================================================

        if not result.success:

            logger.error(
                "Private Agent failed | "
                "user=%s | chat=%s | error=%s",
                user.id,
                chat_id,
                result.error,
            )

            await message.answer(
                "Hozir xabarni qayta ishlashda muammo yuz berdi. "
                "Birozdan keyin yana urinib ko'r."
            )

            return

        # Agent javob bermaslikka qaror qilgan bo'lishi mumkin.
        if not result.should_send:

            logger.debug(
                "Private Agent ignored message | "
                "user=%s | chat=%s",
                user.id,
                chat_id,
            )

            return

        answer = (
            result.response_text or ""
        ).strip()

        if not answer:

            logger.warning(
                "Private Agent returned empty response | "
                "user=%s | chat=%s",
                user.id,
                chat_id,
            )

            return

        # ==================================================
        # SAVE ASSISTANT MESSAGE
        # ==================================================
        #
        # Muhim:
        # Telegram yuborishni Executor/Telegram Tool qiladi.
        # Bu handler yana send_answer() qilmaydi.
        # Shunday qilib DOUBLE MESSAGE bo'lmaydi.
        #

        await message_service.save(
            telegram_message_id=None,
            chat_id=chat_id,
            user_telegram_id=None,
            role="assistant",
            content=answer,
            message_type="text",
            reply_to_message_id=message.message_id,
            is_bot_message=True,
        )

        logger.info(
            "Private Agent response processed | "
            "user=%s | chat=%s | action=%s",
            user.id,
            chat_id,
            getattr(
                result.decision,
                "action",
                None,
            ),
        )

    except Exception:

        logger.exception(
            "Private message processing failed | "
            "user=%s | chat=%s",
            user.id,
            chat_id,
        )

        try:

            await message.answer(
                "Hozir xabarni qayta ishlashda muammo yuz berdi. "
                "Birozdan keyin yana urinib ko'r."
            )

        except Exception:

            logger.exception(
                "Private error message failed."
        )
