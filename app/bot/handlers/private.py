from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import Message

from app.agent.runtime import agent_runtime
from app.ai.engine import ai_engine
from app.bot.sender import send_answer
from app.services.message_service import message_service
from app.services.user_service import user_service

logger = logging.getLogger("sara.bot.private")

router = Router(name="private_messages")


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

    try:

        # ====================================================
        # USER
        # ====================================================

        db_user = await user_service.get_or_create(
            user
        )

        # ====================================================
        # SAVE USER MESSAGE
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
            is_bot_message=False,
        )

        # ====================================================
        # AGENT RUNTIME
        # ====================================================

        is_question = (
            "?" in message.text
            or message.text.lower().startswith(
                (
                    "nima",
                    "nega",
                    "qanday",
                    "qachon",
                    "qayer",
                    "kim",
                    "what",
                    "why",
                    "how",
                    "when",
                    "where",
                    "who",
                )
            )
        )

        agent_context = await agent_runtime.prepare(
            message=message,
            user_id=db_user.telegram_id,
            group_id=None,
            sara_called=True,
            is_question=is_question,
            is_reply_to_sara=False,
        )

        logger.debug(
            "Private Agent Runtime: %s",
            agent_context,
        )

        # ====================================================
        # AI
        # ====================================================

        answer = await ai_engine.generate(
            user_text=message.text,
            chat_id=chat_id,
            user_id=db_user.telegram_id,
            group_id=None,
            source_message_id=saved_message.id,
        )

        if not answer or not answer.strip():
            answer = (
                "Hozircha javob yaratilmadi. "
                "Yana bir marta urinib ko'r."
            )

        # ====================================================
        # AGENT RESPONSE STATE
        # ====================================================

        from app.agent.loop_guard import loop_guard
        from app.agent.proactive import proactive_agent

        loop_guard.register_response(
            chat_id=chat_id
        )

        proactive_agent.record_response(
            chat_id=chat_id
        )

        # ====================================================
        # SAVE ASSISTANT MESSAGE
        # ====================================================

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

        # ====================================================
        # SEND
        # ====================================================

        await send_answer(
            bot=message.bot,
            chat_id=chat_id,
            text=answer,
            reply_to_message_id=message.message_id,
        )

        logger.info(
            "Private AI response sent | user=%s | chat=%s",
            user.id,
            chat_id,
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
