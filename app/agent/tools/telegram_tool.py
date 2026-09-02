from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

logger = logging.getLogger("sara.agent.tools.telegram")


class TelegramTool:
    """
    SARA uchun Telegram action tool.

    SARA quyidagilarni bajara oladi:

    - Telegram chatga xabar yuborish
    - Reply qilish
    - Chatga mustaqil xabar yuborish

    Muhim:
    Bot token bu class ichida saqlanmaydi.
    Telegram Bot obyekti tashqaridan beriladi.
    """

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Telegram chatga xabar yuboradi.
        """

        text = str(text).strip()

        if not text:
            return {
                "success": False,
                "error": "empty_message",
            }

        if len(text) > 4096:
            text = text[:4090] + "..."

        try:
            if reply_to_message_id is not None:
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_to_message_id=reply_to_message_id,
                )
            else:
                message = await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                )

            logger.info(
                "SARA Telegram action | chat=%s | message=%s",
                chat_id,
                message.message_id,
            )

            return {
                "success": True,
                "chat_id": chat_id,
                "message_id": message.message_id,
                "text": text,
            }

        except Exception as exc:
            logger.exception(
                "Telegram send failed | chat=%s",
                chat_id,
            )

            return {
                "success": False,
                "chat_id": chat_id,
                "error": str(exc),
            }


telegram_tool: TelegramTool | None = None


def configure_telegram_tool(bot: Bot) -> TelegramTool:
    """
    Telegram toolni global SARA agent tizimiga ulaydi.
    """

    global telegram_tool

    telegram_tool = TelegramTool(bot)

    logger.info("Telegram Tool configured.")

    return telegram_tool


async def send_telegram_message(
    *,
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
) -> dict[str, Any]:
    """
    Registry orqali chaqiriladigan wrapper.
    """

    if telegram_tool is None:
        return {
            "success": False,
            "error": "telegram_tool_not_configured",
        }

    return await telegram_tool.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
              )
