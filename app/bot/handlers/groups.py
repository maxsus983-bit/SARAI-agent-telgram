from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.types import Message

from app.agent.bot_interaction import (
    bot_interaction,
    is_bot_message,
)
from app.agent.emotional_state import emotional_state
from app.agent.loop_guard import loop_guard
from app.agent.proactive import proactive_agent
from app.ai.engine import ai_engine
from app.bot.sender import send_answer
from app.services.group_service import group_service
from app.services.message_service import message_service
from app.services.user_service import user_service

logger = logging.getLogger("sara.bot.groups")

router = Router(name="group_messages")


SARA_WORD_PATTERN = re.compile(
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

    # "sara"
    if SARA_WORD_PATTERN.search(text):
        return True

    # "@sara_username"
    username = await get_sara_username(
        message
    )

    if username:
        if (
            f"@{username.lower()}"
            in text.lower()
        ):
            return True

    # SARA xabariga reply
    if message.reply_to_message:
        replied = (
            message.reply_to_message
            .from_user
        )

        if replied:
            if replied.is_bot:
                sara_username = await get_sara_username(
                    message
                )

                if (
                    sara_username
                    and replied.username
                    and replied.username.lower()
                    == sara_username.lower()
                ):
                    return True

    return False


def clean_group_message(
    message: Message,
) -> str:

    text = message.text or ""

    text = SARA_WORD_PATTERN.sub(
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
    ).strip()

    return text


def looks_like_question(
    text: str,
) -> bool:

    if not text:
        return False

    if "?" in text:
        return True

    question_words = (
        "nima",
        "nega",
        "qanday",
        "qachon",
        "qayerda",
        "kim",
        "qancha",
        "mumkinmi",
        "ayt",
        "bilasanmi",
        "what",
        "why",
        "how",
        "when",
        "where",
        "who",
        "can you",
        "почему",
        "как",
        "когда",
        "где",
        "кто",
    )

    lowered = text.lower()

    return any(
        lowered.startswith(word + " ")
        or lowered == word
        for word in question_words
    )


def is_reply_to_sara(
    message: Message,
) -> bool:

    if not message.reply_to_message:
        return False

    replied = (
        message.reply_to_message
        .from_user
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


async def process_group_message(
    message: Message,
) -> None:

    if message.from_user is None:
        return

    if not message.text:
        return

    user = message.from_user
    chat = message.chat
    chat_id = chat.id

    # User gapirsa bot chain uziladi.
    loop_guard.register_user_message(
        chat_id=chat_id
    )

    proactive_agent.record_activity(
        chat_id=chat_id
    )

    try:
        db_group = (
            await group_service.get_or_create(
                chat
            )
        )

        db_user = (
            await user_service.get_or_create(
                user
            )
        )

        saved_message = (
            await message_service.save(
                telegram_message_id=(
                    message.message_id
                ),
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
                is_bot_message=False,
            )
        )

        called = await is_sara_called(
            message
        )

        reply_to_sara = is_reply_to_sara(
            message
        )

        question = looks_like_question(
            message.text
        )

        # --------------------------------------------------
        # BOT MESSAGE
        # --------------------------------------------------

        if is_bot_message(message):

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

        # --------------------------------------------------
        # PROACTIVE DECISION
        # --------------------------------------------------

        decision = proactive_agent.decide(
            chat_id=chat_id,
            group_enabled=db_group.enabled,
            quiet_mode=db_group.quiet_mode,
            sara_called=called,
            message_is_question=question,
            message_is_reply_to_sara=reply_to_sara,
        )

        if not decision.should_respond:
            return

        # --------------------------------------------------
        # LOOP PROTECTION
        # --------------------------------------------------

        if not loop_guard.can_respond(
            chat_id=chat_id,
            is_bot_message=is_bot_message(
                message
            ),
        ):
            logger.warning(
                "Group response blocked by LoopGuard | "
                "chat=%s",
                chat_id,
            )
            return

        # --------------------------------------------------
        # CLEAN INPUT
        # --------------------------------------------------

        cleaned_text = clean_group_message(
            message
        )

        if not cleaned_text:

            if called:
                cleaned_text = (
                    "Meni chaqirishdi. "
                    "Guruhdagi suhbatni hisobga olib "
                    "foydali javob ber."
                )

            else:
                cleaned_text = (
                    "Guruhdagi suhbatga mos ravishda "
                    "qisqa va tabiiy javob ber."
                )

        # --------------------------------------------------
        # EMOTIONAL STATE
        # --------------------------------------------------

        emotional_state.update(
            chat_id=chat_id,
            user_id=user.id,
            mood=(
                "curious"
                if question
                else "neutral"
            ),
            intensity_change=(
                0.08
                if question
                else 0.01
            ),
            curiosity_change=(
                0.10
                if question
                else 0.02
            ),
        )

        # --------------------------------------------------
        # AI
        # --------------------------------------------------

        answer = await ai_engine.generate(
            user_text=cleaned_text,
            chat_id=chat_id,
            user_id=db_user.telegram_id,
            group_id=db_group.telegram_id,
            source_message_id=saved_message.id,
        )

        if not answer.strip():
            return

        # --------------------------------------------------
        # LOOP STATE
        # --------------------------------------------------

        loop_guard.register_response(
            chat_id=chat_id
        )

        loop_guard.register_bot_message(
            chat_id=chat_id
        )

        proactive_agent.record_response(
            chat_id=chat_id
        )

        if is_bot_message(message):
            bot_interaction.register_response(
                chat_id=chat_id
            )

        # --------------------------------------------------
        # SAVE AI MESSAGE
        # --------------------------------------------------

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

        # --------------------------------------------------
        # SEND
        # --------------------------------------------------

        await send_answer(
            bot=message.bot,
            chat_id=chat_id,
            text=answer,
            reply_to_message_id=(
                message.message_id
            ),
        )

        logger.info(
            "Group AI response sent | "
            "chat=%s | user=%s | reason=%s",
            chat_id,
            user.id,
            decision.reason,
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
                "Hozir xabarni qayta ishlashda "
                "muammo yuz berdi."
            )

        except Exception:
            logger.exception(
                "Group error message failed."
            )


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
