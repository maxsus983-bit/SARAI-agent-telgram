from __future__ import annotations

import base64
import logging
from typing import Any

from app.ai.openrouter import OpenRouterError, openrouter

logger = logging.getLogger("sara.media.vision")


def image_to_data_url(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")

    return (
        f"data:{mime_type};base64,{encoded}"
    )


async def analyze_image(
    *,
    image_bytes: bytes,
    prompt: str | None = None,
    mime_type: str = "image/jpeg",
) -> str:
    """
    Rasmni OpenRouter vision modeliga yuboradi.
    """

    if not image_bytes:
        raise ValueError("Image bytes bo'sh.")

    if prompt is None:
        prompt = (
            "Bu rasmni batafsil tahlil qil. "
            "Unda nima borligini, odamlar, obyektlar, "
            "muhit, yozuvlar va muhim tafsilotlarni ayt. "
            "Agar rasmda matn bo'lsa, uni ham o'qib ber. "
            "Javobni foydalanuvchi tiliga mos ber."
        )

    image_url = image_to_data_url(
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                    },
                },
            ],
        }
    ]

    try:
        result = await openrouter.chat(
            messages=messages,
        )

        return result.text.strip()

    except OpenRouterError:
        logger.exception(
            "Vision OpenRouter request failed."
        )

        raise
