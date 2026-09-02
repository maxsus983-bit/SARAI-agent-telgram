from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import Message

from app.ai.engine import ai_engine
from app.bot.sender import send_answer
from app.services.message_service import message_service
from app.services.user_service import user_service


logger = logging.getLogger("sara.bot.private")

router = Router(name="private_messages")


@router.message(lambda message: message.chat.type == "private")
async def handle_private_message(message: Message) -> None:
    """
    SARA AI — Private Chat Handler

    Vazifalari:
    - Foydalanuvchini DB ga saqlash/yangilash
    - Xabarni DB ga saqlash
    - AI ga yuborish
    - AI javobini DB ga saqlash
    - Telegramga javob yuborish
    """

    # Faqat haqiqiy foydalanuvchi xabarlarini qayta ishlaymiz
    if message.from_user is None:
        return

    # Hozircha text xabarlar bilan ishlaymiz.
    # Media keyingi bosqichda alohida handler orqali ishlanadi.
    if not message.text:
        return

    user = message.from_user
    chat_id = message.chat.id

    try:
        # =========================================================
        # 1. USERNI DATABASE GA SAQLASH
        # =========================================================

        db_user = await user_service.get_or_create(user)

        # =========================================================
        # 2. USER XABARINI DATABASE GA SAQLASH
        # =========================================================

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

        # =========================================================
        # 3. AI GA XABAR YUBORISH
        # =========================================================

        answer = await ai_engine.generate(
            user_text=message.text,
            chat_id=chat_id,
            user_id=db_user.telegram_id,
            group_id=None,
            source_message_id=saved_message.id,
        )

        # =========================================================
        # 4. AI JAVOBINI DATABASE GA SAQLASH
        # =========================================================

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

        # =========================================================
        # 5. TELEGRAMGA JAVOB YUBORISH
        # =========================================================

        await send_answer(
            bot=message.bot,
            chat_id=chat_id,
            text=answer,
            reply_to_message_id=message.message_id,
        )

        logger.info(
            "Private message processed | user=%s | chat=%s",
            user.id,
            chat_id,
        )

    except Exception:
        logger.exception(
            "Private message processing failed | user=%s | chat=%s",
            user.id,
            chat_id,
        )

        # Foydalanuvchiga ichki xatoni ko'rsatmaymiz.
        try:
            await message.answer(
                "Hozircha xabarni qayta ishlashda muammo yuz berdi. "
                "Birozdan keyin yana urinib ko‘r."
            )
        except Exception:
            logger.exception("Failed to send private error message.")
