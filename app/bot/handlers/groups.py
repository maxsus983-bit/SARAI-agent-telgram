from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.types import Message

from app.ai.engine import ai_engine
from app.bot.sender import send_answer
from app.services.group_service import group_service
from app.services.message_service import message_service
from app.services.user_service import user_service


logger = logging.getLogger("sara.bot.groups")

router = Router(name="group_messages")


# ================================================================
# SARA MENTION / CALL DETECTION
# ================================================================

SARA_WORD_PATTERN = re.compile(
    r"(?<!\w)sara(?!\w)",
    re.IGNORECASE,
)


def is_sara_called(message: Message) -> bool:
    """
    SARA chaqirilganligini aniqlaydi.

    Quyidagilar ishlaydi:

        sara
        Sara
        SARA
        @sara_bot
        sara yordam ber
        @sara_bot nima deb o'ylaysan?

    Bundan tashqari:
    - SARA yozgan xabarga reply
    """

    if message.from_user is None:
        return False

    # ------------------------------------------------------------
    # 1. SARA botiga reply qilinganmi?
    # ------------------------------------------------------------

    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user

        if replied_user and replied_user.is_bot:
            return True

    # ------------------------------------------------------------
    # 2. Text yo'q bo'lsa, chaqiruvni aniqlab bo'lmaydi
    # ------------------------------------------------------------

    if not message.text:
        return False

    text = message.text.strip()

    if not text:
        return False

    # ------------------------------------------------------------
    # 3. "sara" so'zi
    # ------------------------------------------------------------

    if SARA_WORD_PATTERN.search(text):
        return True

    # ------------------------------------------------------------
    # 4. @bot_username orqali mention
    # ------------------------------------------------------------

    if message.bot:
        bot_username = None

        # Telegram bot username'ini olishga har safar API chaqirmaslik
        # uchun oddiy cache ishlatamiz.
        bot_username = getattr(message.bot, "_sara_username", None)

        if not bot_username:
            try:
                bot_info = await_bot_info(message)
                bot_username = bot_info
            except Exception:
                bot_username = None

        if bot_username:
            mention = f"@{bot_username.lower()}"

            if mention in text.lower():
                return True

    return False


async def await_bot_info(message: Message) -> str | None:
    """
    Bot username'ini olish.

    Ayrim holatlarda message.bot username'ini to'g'ridan-to'g'ri
    bermaydi, shuning uchun get_me() ishlatiladi.
    """

    try:
        me = await message.bot.get_me()

        username = me.username

        if username:
            setattr(message.bot, "_sara_username", username)
            return username

    except Exception:
        logger.exception("Failed to get bot information.")

    return None


def clean_group_message(message: Message) -> str:
    """
    AI ga yuborishdan oldin SARA chaqiruvini olib tashlaydi.

    Masalan:

        "sara bugun nima qilamiz?"

    ->

        "bugun nima qilamiz?"

    @sara_bot mention ham olib tashlanadi.
    """

    text = message.text or ""

    # "sara" so'zini olib tashlash
    text = SARA_WORD_PATTERN.sub("", text)

    # @username mentionini olib tashlash
    if message.bot:
        username = getattr(message.bot, "_sara_username", None)

        if username:
            text = re.sub(
                rf"@{re.escape(username)}",
                "",
                text,
                flags=re.IGNORECASE,
            )

    # Ortiqcha bo'shliqlar
    text = re.sub(r"\s+", " ", text).strip()

    return text


@router.message(
    lambda message: message.chat.type in {"group", "supergroup"}
)
async def handle_group_message(message: Message) -> None:
    """
    SARA AI — Group / Supergroup Handler.

    Guruhdagi barcha text xabarlarni DB ga yozadi.

    Ammo AI faqat:
    - "sara" deyilganda
    - @sara_bot mention qilinganda
    - SARA xabariga reply qilinganda

    javob beradi.
    """

    if message.from_user is None:
        return

    if not message.text:
        return

    user = message.from_user
    chat = message.chat
    chat_id = chat.id

    try:
        # =========================================================
        # 1. GROUPNI DATABASE GA SAQLASH
        # =========================================================

        db_group = await group_service.get_or_create(chat)

        # =========================================================
        # 2. USERNI DATABASE GA SAQLASH
        # =========================================================

        db_user = await user_service.get_or_create(user)

        # =========================================================
        # 3. GURUH XABARINI DATABASE GA SAQLASH
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
        # 4. SARA CHAQRILGANMI?
        # =========================================================

        called = await is_sara_called(message)

        # SARA chaqirilmagan bo'lsa:
        # xabar DB da qoladi, lekin AI javob bermaydi.
        if not called:
            return

        # =========================================================
        # 5. SARA MENTIONINI TOZALASH
        # =========================================================

        cleaned_text = clean_group_message(message)

        # Agar xabarda faqat "sara" bo'lgan bo'lsa
        if not cleaned_text:
            cleaned_text = (
                "Meni chaqirishdi. Guruhdagi suhbatni hisobga olib "
                "foydali javob ber."
            )

        # =========================================================
        # 6. AI GA YUBORISH
        # =========================================================

        answer = await ai_engine.generate(
            user_text=cleaned_text,
            chat_id=chat_id,
            user_id=db_user.telegram_id,
            group_id=db_group.telegram_id,
            source_message_id=saved_message.id,
        )

        # =========================================================
        # 7. AI JAVOBINI DATABASE GA SAQLASH
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
        # 8. GURUHGA JAVOB YUBORISH
        # =========================================================

        await send_answer(
            bot=message.bot,
            chat_id=chat_id,
            text=answer,
            reply_to_message_id=message.message_id,
        )

        logger.info(
            "Group message processed | user=%s | group=%s",
            user.id,
            chat_id,
        )

    except Exception:
        logger.exception(
            "Group message processing failed | user=%s | group=%s",
            user.id,
            chat_id,
        )

        try:
            await message.answer(
                "Xabarni qayta ishlashda muammo yuz berdi."
            )
        except Exception:
            logger.exception("Failed to send group error message.")
