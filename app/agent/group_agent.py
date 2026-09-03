from __future__ import annotations

import logging
from typing import Any

from aiogram.types import Message

from app.agent.telegram_bridge import process_group_message

logger = logging.getLogger("sara.agent.group_agent")


class GroupAgent:
    """
    SARA'ning guruhdagi mustaqil Agent qatlami.

    SARA:
      - mention/reply bo'lsa javob berishi mumkin;
      - savol bo'lsa javob berishi mumkin;
      - suhbatni kuzatib, proactive ravishda qo'shilishi mumkin;
      - bot-loop himoyasidan foydalanadi;
      - private user memory'ni guruhga oshkor qilmaydi.
    """

    async def process(
        self,
        message: Message,
        *,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        proactive_allowed: bool = True,
        activity_context: dict[str, Any] | None = None,
    ):
        text = message.text or message.caption or ""

        if not text.strip():
            return None

        flags: dict[str, Any] = {
            "source": "telegram_group",
            "group_chat_id": message.chat.id,
            "message_id": message.message_id,
        }

        if activity_context:
            flags.update(activity_context)

        try:
            result = await process_group_message(
                message,
                sara_called=sara_called,
                is_reply_to_sara=is_reply_to_sara,
                proactive_allowed=proactive_allowed,
                extra_flags=flags,
            )

            if result.success:
                logger.debug(
                    "Group Agent processed | "
                    "chat=%s | send=%s",
                    message.chat.id,
                    result.should_send,
                )
            else:
                logger.warning(
                    "Group Agent failed | "
                    "chat=%s | error=%s",
                    message.chat.id,
                    result.error,
                )

            return result

        except Exception:
            logger.exception(
                "Group Agent exception | chat=%s",
                message.chat.id,
            )
            return None


group_agent = GroupAgent()
