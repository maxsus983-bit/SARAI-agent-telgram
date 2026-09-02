from __future__ import annotations

import logging
import re

from aiogram import Router
from aiogram.types import Message

from app.media.processor import media_processor
from app.services.message_service import message_service
from app.services.user_service import user_service
from app.services.group_service import group_service

logger = logging.getLogger("sara.bot.media")

router = Router(name="media")


OCR_PATTERN = re.compile(
    r"\b(ocr|matnni\s+o['’]?qi|matnni\s+chiqar|"
    r"yozuvni\s+o['’]?qi|textni\s+o['’]?qi)\b",
    re.IGNORECASE,
)


def wants_ocr(message: Message) -> bool:
    caption = message.caption or ""
    return bool(OCR_PATTERN.search(caption))


def get_media_prompt(message: Message) -> str | None:
    caption = (message.caption or "").strip()

    if not caption:
        return None

    if wants_ocr(message):
        return None

    return (
        "Foydalanuvchi rasmga quyidagi topshiriq berdi:\n\n"
        f"{caption}\n\n"
        "Rasmni ko'rib, aynan shu topshiriqni bajar."
    )


async def save_media_message(
    message: Message,
    *,
    user_id: int,
    chat_id: int,
    media_type: str,
    metadata: dict,
) -> int | None:
    try:
        saved = await message_service.save(
            telegram_message_id=message.message_id,
            chat_id=chat_id,
            user_telegram_id=user_id,
            role="user",
            content=str(metadata),
            message_type=media_type,
            reply_to_message_id=(
                message.reply_to_message.message_id
                if message.reply_to_message
                else None
            ),
            is_bot_message=False,
        )

        return saved.id

    except Exception:
        logger.exception(
            "Media message DBga saqlanmadi."
        )
        return None


@router.message(
    lambda message: bool(message.photo)
)
async def handle_photo(message: Message) -> None:
    if message.from_user is None:
        return

    if not message.bot:
        return

    user = message.from_user
    chat = message.chat

    try:
        await user_service.get_or_create(user)

        if chat.type in {"group", "supergroup"}:
            await group_service.get_or_create(chat)

        result = await media_processor.process(
            message,
            prompt=get_media_prompt(message),
            ocr=wants_ocr(message),
        )

        if not result.get("supported"):
            await message.answer(
                "❌ Bu rasmni qayta ishlay olmadim."
            )
            return

        metadata = result.get("metadata", {})

        source_message_id = await save_media_message(
            message,
            user_id=user.id,
            chat_id=chat.id,
            media_type="photo",
            metadata=metadata,
        )

        answer = result.get("result")

        if not answer:
            answer = (
                "Rasmni qabul qildim, "
                "lekin undan natija olishning iloji bo'lmadi."
            )

        await message.answer(
            answer,
            reply_to_message_id=message.message_id,
        )

        if source_message_id:
            try:
                await message_service.save(
                    telegram_message_id=None,
                    chat_id=chat.id,
                    user_telegram_id=None,
                    role="assistant",
                    content=answer,
                    message_type="text",
                    reply_to_message_id=message.message_id,
                    is_bot_message=True,
                )
            except Exception:
                logger.exception(
                    "Media AI javobi DBga saqlanmadi."
                )

        logger.info(
            "Photo processed | user=%s | chat=%s | ocr=%s",
            user.id,
            chat.id,
            wants_ocr(message),
        )

    except Exception:
        logger.exception(
            "Photo processing failed | user=%s | chat=%s",
            user.id,
            chat.id,
        )

        try:
            await message.answer(
                "🖼 Rasmni tahlil qilishda xatolik yuz berdi. "
                "Birozdan keyin yana urinib ko'r."
            )
        except Exception:
            logger.exception(
                "Photo error response failed."
            )


@router.message(
    lambda message: (
        bool(message.document)
        and bool(message.document.mime_type)
        and message.document.mime_type.startswith("image/")
    )
)
async def handle_image_document(message: Message) -> None:
    if message.from_user is None:
        return

    user = message.from_user
    chat = message.chat

    try:
        await user_service.get_or_create(user)

        if chat.type in {"group", "supergroup"}:
            await group_service.get_or_create(chat)

        result = await media_processor.process(
            message,
            prompt=get_media_prompt(message),
            ocr=wants_ocr(message),
        )

        if not result.get("supported"):
            await message.answer(
                "❌ Bu rasm faylini qayta ishlay olmadim."
            )
            return

        metadata = result.get("metadata", {})

        await save_media_message(
            message,
            user_id=user.id,
            chat_id=chat.id,
            media_type="image_document",
            metadata=metadata,
        )

        answer = result.get("result")

        if not answer:
            answer = (
                "Rasm faylini qabul qildim, "
                "lekin natija olinmadi."
            )

        await message.answer(
            answer,
            reply_to_message_id=message.message_id,
        )

        try:
            await message_service.save(
                telegram_message_id=None,
                chat_id=chat.id,
                user_telegram_id=None,
                role="assistant",
                content=answer,
                message_type="text",
                reply_to_message_id=message.message_id,
                is_bot_message=True,
            )
        except Exception:
            logger.exception(
                "Document AI javobi DBga saqlanmadi."
            )

    except Exception:
        logger.exception(
            "Image document processing failed."
        )

        try:
            await message.answer(
                "🖼 Rasm faylini tahlil qilishda "
                "xatolik yuz berdi."
            )
        except Exception:
            logger.exception(
                "Image document error response failed."
            )


@router.message(
    lambda message: bool(message.sticker)
)
async def handle_sticker(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        result = await media_processor.process(
            message
        )

        metadata = result.get("metadata", {})

        await save_media_message(
            message,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            media_type="sticker",
            metadata=metadata,
        )

        await message.answer(
            "😄 Sticker qabul qilindi."
        )

    except Exception:
        logger.exception(
            "Sticker processing failed."
        )


@router.message(
    lambda message: bool(message.animation)
)
async def handle_animation(message: Message) -> None:
    if message.from_user is None:
        return

    try:
        result = await media_processor.process(
            message
        )

        metadata = result.get("metadata", {})

        await save_media_message(
            message,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            media_type="animation",
            metadata=metadata,
        )

        await message.answer(
            "🎞 GIF/animation qabul qilindi."
        )

    except Exception:
        logger.exception(
            "Animation processing failed."
      )
