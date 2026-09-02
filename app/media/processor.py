from __future__ import annotations

import io
import logging
from typing import Any

from aiogram import Bot
from aiogram.types import Message

from app.media.metadata import (
    MediaMetadata,
    animation_metadata,
    document_metadata,
    metadata_to_dict,
    photo_metadata,
    sticker_metadata,
)
from app.media.ocr import extract_text_from_image
from app.media.vision import analyze_image

logger = logging.getLogger("sara.media.processor")


class MediaProcessor:

    async def download_file(
        self,
        bot: Bot,
        file_id: str,
    ) -> bytes:
        """
        Telegram file'ni RAMga yuklaydi.
        """

        telegram_file = await bot.get_file(file_id)

        buffer = io.BytesIO()

        await bot.download(
            telegram_file,
            destination=buffer,
        )

        return buffer.getvalue()

    def detect(
        self,
        message: Message,
    ) -> MediaMetadata | None:

        if message.photo:
            return photo_metadata(message)

        if message.document:
            return document_metadata(message)

        if message.sticker:
            return sticker_metadata(message)

        if message.animation:
            return animation_metadata(message)

        return None

    async def process_photo(
        self,
        message: Message,
        *,
        prompt: str | None = None,
        ocr: bool = False,
    ) -> dict[str, Any]:

        if not message.photo:
            raise ValueError(
                "Message ichida photo mavjud emas."
            )

        metadata = photo_metadata(message)

        image_bytes = await self.download_file(
            bot=message.bot,
            file_id=metadata.file_id,
        )

        if ocr:
            result = await extract_text_from_image(
                image_bytes=image_bytes,
                mime_type="image/jpeg",
            )
        else:
            result = await analyze_image(
                image_bytes=image_bytes,
                prompt=prompt,
                mime_type="image/jpeg",
            )

        return {
            "metadata": metadata_to_dict(metadata),
            "result": result,
            "ocr": ocr,
        }

    async def process_image_document(
        self,
        message: Message,
        *,
        prompt: str | None = None,
        ocr: bool = False,
    ) -> dict[str, Any]:

        if not message.document:
            raise ValueError(
                "Message ichida document mavjud emas."
            )

        metadata = document_metadata(message)

        if not metadata.mime_type:
            raise ValueError(
                "Document MIME type mavjud emas."
            )

        if not metadata.mime_type.startswith("image/"):
            raise ValueError(
                "Document image emas."
            )

        image_bytes = await self.download_file(
            bot=message.bot,
            file_id=metadata.file_id,
        )

        if ocr:
            result = await extract_text_from_image(
                image_bytes=image_bytes,
                mime_type=metadata.mime_type,
            )
        else:
            result = await analyze_image(
                image_bytes=image_bytes,
                prompt=prompt,
                mime_type=metadata.mime_type,
            )

        return {
            "metadata": metadata_to_dict(metadata),
            "result": result,
            "ocr": ocr,
        }

    async def process(
        self,
        message: Message,
        *,
        prompt: str | None = None,
        ocr: bool = False,
    ) -> dict[str, Any]:

        metadata = self.detect(message)

        if metadata is None:
            return {
                "supported": False,
                "message": (
                    "Bu media turi hozircha "
                    "qo'llab-quvvatlanmaydi."
                ),
            }

        if message.photo:
            result = await self.process_photo(
                message,
                prompt=prompt,
                ocr=ocr,
            )

            result["supported"] = True
            return result

        if (
            message.document
            and metadata.mime_type
            and metadata.mime_type.startswith("image/")
        ):
            result = await self.process_image_document(
                message,
                prompt=prompt,
                ocr=ocr,
            )

            result["supported"] = True
            return result

        if message.sticker:
            return {
                "supported": True,
                "metadata": metadata_to_dict(metadata),
                "result": (
                    "Bu sticker. "
                    "Sticker metadata olindi."
                ),
            }

        if message.animation:
            return {
                "supported": True,
                "metadata": metadata_to_dict(metadata),
                "result": (
                    "Bu GIF/animation. "
                    "Animation metadata olindi."
                ),
            }

        return {
            "supported": True,
            "metadata": metadata_to_dict(metadata),
            "result": (
                "Media qabul qilindi, "
                "lekin AI tahlili hozircha mavjud emas."
            ),
        }


media_processor = MediaProcessor()
