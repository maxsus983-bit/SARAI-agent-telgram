from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.types import Message

from app.agent.bot_interaction import (
    bot_interaction,
    is_bot_message,
)
from app.agent.loop_guard import loop_guard
from app.agent.proactive import proactive_agent
from app.agent.group_agent import group_agent
from app.services.group_service import group_service
from app.services.message_service import message_service
from app.services.user_service import user_service

logger = logging.getLogger("sara.bot.groups")

router = Router(name="group_messages")


# ============================================================
# SARA DETECTION
# ============================================================

SARA_PATTERN = re.compile(
    r"(?<!\w)sara(?!\w)",
    re.IGNORECASE,
)


async def get_sara_username(
    message: Message,
) -> str | None:

    cached = getattr(
        message.bot,
        "_sara_username",
        None,
    )

    if cached:
        return cached

    try:

        me = await message.bot.get_me()

        if me.username:

            setattr(
                message.bot,
                "_sara_username",
                me.username,
            )

            return me.username

    except Exception:

        logger.exception(
            "SARA username olishda xato."
        )

    return None


async def is_sara_called(
    message: Message,
) -> bool:

    if message.from_user is None:
        return False

    text = message.text or ""

    if not text:
        return False

    # "sara" yozilgan bo'lsa
    if SARA_PATTERN.search(text):
        return True

    # @sara yozilgan bo'lsa
    username = await get_sara_username(
        message
    )

    if username:

        if (
            f"@{username.lower()}"
            in text.lower()
        ):
            return True

    # SARA xabariga reply bo'lsa
    if message.reply_to_message:

        replied_user = (
            message.reply_to_message.from_user
        )

        if replied_user and replied_user.is_bot:

            if (
                username
                and replied_user.username
                and replied_user.username.lower()
                == username.lower()
            ):
                return True

    return False


def is_reply_to_sara(
    message: Message,
) -> bool:

    if not message.reply_to_message:
        return False

    replied = (
        message.reply_to_message.from_user
    )

    if not replied:
        return False

    if not replied.is_bot:
        return False

    username = getattr(
        message.bot,
        "_sara_username",
        None,
    )

    if not username:
        return False

    return bool(
        replied.username
        and replied.username.lower()
        == username.lower()
    )


def clean_message(
    message: Message,
) -> str:

    text = message.text or ""

    # sara so'zini olib tashlash
    text = SARA_PATTERN.sub(
        "",
        text,
    )

    username = getattr(
        message.bot,
        "_sara_username",
        None,
    )

    if username:

        text = re.sub(
            rf"@{re.escape(username)}",
            "",
            text,
            flags=re.IGNORECASE,
        )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def looks_like_question(
    text: str,
) -> bool:

    if not text:
        return False

    if "?" in text:
        return True

    lowered = text.lower()

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
        lowered == word
        or lowered.startswith(word + " ")
        for word in question_words
    )


# ============================================================
# GROUP MESSAGE
# ============================================================

async def process_group_message(
    message: Message,
) -> None:

    if message.from_user is None:
        return

    if not message.text:
        return

    user = message.from_user
    chat_id = message.chat.id

    try:

        # ====================================================
        # USER
        # ====================================================

        db_user = await user_service.get_or_create(
            user
        )

        # ====================================================
        # GROUP
        # ====================================================

        db_group = await group_service.get_or_create(
            message.chat
        )

        # ====================================================
        # DETECTION
        # ====================================================

        called = await is_sara_called(
            message
        )

        reply_to_sara = is_reply_to_sara(
            message
        )

        question = looks_like_question(
            message.text
        )

        bot_message = is_bot_message(
            message
        )

        # ====================================================
        # BOT → BOT
        # ====================================================

        if bot_message:

            if not bot_interaction.should_process(
                message=message,
                sara_username=await get_sara_username(
                    message
                ),
            ):
                return

            bot_interaction.register_incoming_bot(
                message=message
            )

        # ====================================================
        # SAVE MESSAGE
        # ====================================================

        saved_message = await message_service.save(
            telegram_message_id=message.message_id,
            chat_id=chat_id,
            user_telegram_id=user.id,
            role="user",
            content=message.text,
            message_type="text",
            reply_to_message_id=(
                message.reply_to_message.message_id
                if message.reply_to_message
                else None
            ),
            is_bot_message=bot_message,
        )

        # ====================================================
        # PROACTIVE DECISION
        # ====================================================

        decision = proactive_agent.decide(
            chat_id=chat_id,
            group_enabled=db_group.enabled,
            quiet_mode=db_group.quiet_mode,
            sara_called=called,
            message_is_question=question,
            message_is_reply_to_sara=reply_to_sara,
            is_bot_message=bot_message,
        )

        if not decision.should_respond:

            logger.debug(
                "Proactive Agent decided to ignore | "
                "chat=%s | reason=%s",
                chat_id,
                decision.reason,
            )

            return

        # ====================================================
        # LOOP GUARD
        # ====================================================

        if not loop_guard.can_respond(
            chat_id=chat_id,
            is_bot_message=bot_message,
        ):

            logger.warning(
                "Response blocked by LoopGuard | "
                "chat=%s",
                chat_id,
            )

            return

        # ====================================================
        # CLEAN MESSAGE
        # ====================================================

        cleaned_text = clean_message(
            message
        )

        if not cleaned_text:

            if called or reply_to_sara:

                cleaned_text = (
                    "Guruhdagi suhbatni hisobga olib "
                    "foydali va tabiiy javob ber."
                )

            else:

                cleaned_text = (
                    "Guruhdagi suhbatga mos "
                    "qisqa va tabiiy javob ber."
                )

        # ====================================================
        # AGENT
        # ====================================================
        #
        # Bu yerda endi:
        #
        # Runtime
        #   ↓
        # Brain
        #   ↓
        # Planner
        #   ↓
        # Executor
        #
        # ishlaydi.
        #

        result = await group_agent.process(
            message=message,
            sara_called=called,
            is_reply_to_sara=reply_to_sara,
            proactive_allowed=True,
            activity_context={
                "source": "telegram_group",

                "source_message_id": saved_message.id,

                "cleaned_text": cleaned_text,

                "is_question": question,

                "is_bot_message": bot_message,

                # User memory guruh agentiga beriladi.
                "allow_user_memory": True,

                # Group memory ham beriladi.
                "allow_group_memory": True,

                # Conversation memory.
                "allow_conversation_memory": True,

                # Kelajakdagi long-term memory.
                "remember_context": True,

                # User + Group + Conversation.
                "memory_scope": (
                    "user_and_group_and_conversation"
                ),
            },
        )

        # ====================================================
        # AGENT RESULT
        # ====================================================

        if not result.success:

            logger.error(
                "Group Agent failed | "
                "chat=%s | user=%s | error=%s",
                chat_id,
                user.id,
                result.error,
            )

            return

        if not result.should_send:

            return

        answer = (
            result.response_text or ""
        ).strip()

        if not answer:
            return

        # ====================================================
        # REGISTER RESPONSE
        # ====================================================

        loop_guard.register_response(
            chat_id=chat_id
        )

        loop_guard.register_bot_message(
            chat_id=chat_id
        )

        proactive_agent.record_response(
            chat_id=chat_id
        )

        if bot_message:

            bot_interaction.register_response(
                chat_id=chat_id
            )

        # ====================================================
        # SAVE ASSISTANT MESSAGE
        # ====================================================
        #
        # Telegram Tool orqali javob yuboriladi.
        # Bu yerda faqat DB historyga yozamiz.
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
            "Group Agent response processed | "
            "chat=%s | user=%s | action=%s",
            chat_id,
            user.id,
            getattr(
                result.decision,
                "action",
                None,
            ),
        )

    except Exception:

        logger.exception(
            "Group message processing failed | "
            "chat=%s | user=%s",
            chat_id,
            user.id,
        )

        try:

            await message.answer(
                "Hozir xabarni qayta ishlashda muammo yuz berdi."
            )

        except Exception:

            logger.exception(
                "Group error message failed."
            )


# ============================================================
# TELEGRAM HANDLER
# ============================================================

@router.message(
    lambda message: (
        message.chat.type
        in {"group", "supergroup"}
        and bool(message.from_user)
        and bool(message.text)
    )
)
async def handle_group_message(
    message: Message,
) -> None:

    await process_group_message(
        message
                )
