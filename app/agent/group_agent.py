from __future__ import annotations

import logging
from typing import Any

from aiogram.types import Message

from app.agent.telegram_bridge import process_group_message
from app.agent.message_processor import ProcessedTelegramMessage


logger = logging.getLogger("sara.agent.group_agent")


class GroupAgent:
    """
    SARA Group Agent.

    Vazifalari:

    - Guruh xabarlarini Agent pipeline'ga yuborish
    - SARA mention/reply holatini uzatish
    - Proactive mode'ni uzatish
    - User memory + Group memory + Conversation memory
      ishlashiga imkon berish
    - Group context'ni Agent'ga yetkazish

    Oqim:

        Telegram Group
              ↓
        Group Handler
              ↓
        GroupAgent
              ↓
        Telegram Bridge
              ↓
        Message Processor
              ↓
        Orchestrator
              ↓
        Brain
              ↓
        Planner
              ↓
        Executor
    """

    def __init__(self) -> None:
        self._processed_messages = 0
        self._successful_messages = 0
        self._failed_messages = 0

    # ========================================================
    # MAIN
    # ========================================================

    async def process(
        self,
        message: Message,
        *,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        proactive_allowed: bool = True,
        activity_context: dict[str, Any] | None = None,
    ) -> ProcessedTelegramMessage:

        if message is None:
            return ProcessedTelegramMessage(
                success=False,
                should_send=False,
                error="message_missing",
            )

        if message.from_user is None:
            return ProcessedTelegramMessage(
                success=False,
                should_send=False,
                error="user_missing",
            )

        text = (
            message.text
            or message.caption
            or ""
        ).strip()

        if not text:
            return ProcessedTelegramMessage(
                success=False,
                should_send=False,
                error="empty_message",
            )

        self._processed_messages += 1

        group_id = int(message.chat.id)
        user_id = int(message.from_user.id)

        context: dict[str, Any] = {
            "source": "group_agent",
            "group_id": group_id,
            "chat_id": group_id,
            "user_id": user_id,

            "source_message_id": message.message_id,
            "telegram_message_id": message.message_id,

            "sara_called": sara_called,
            "is_reply_to_sara": is_reply_to_sara,

            "proactive_allowed": proactive_allowed,

            # ------------------------------------------------
            # MEMORY POLICY
            # ------------------------------------------------
            #
            # User xotirasi guruh contextida ham ishlatilishi
            # mumkin.
            #
            # Group xotirasi ham ishlatiladi.
            #
            # Conversation history ham ishlatiladi.
            #
            "allow_user_memory": True,
            "allow_group_memory": True,
            "allow_conversation_memory": True,
            "remember_context": True,

            "memory_scope": (
                "user_and_group_and_conversation"
            ),
        }

        if activity_context:
            context.update(
                activity_context
            )

        try:
            result = await process_group_message(
                message,
                sara_called=sara_called,
                is_reply_to_sara=is_reply_to_sara,
                proactive_allowed=proactive_allowed,
                text=text,
                activity_context=context,
            )

            if result.success:
                self._successful_messages += 1
            else:
                self._failed_messages += 1

            return result

        except Exception as exc:
            self._failed_messages += 1

            logger.exception(
                "Group Agent failed | "
                "group=%s user=%s message=%s",
                group_id,
                user_id,
                message.message_id,
            )

            return ProcessedTelegramMessage(
                success=False,
                should_send=False,
                error=str(exc),
                metadata={
                    "group_id": group_id,
                    "chat_id": group_id,
                    "user_id": user_id,
                    "message_id": message.message_id,
                },
            )

    # ========================================================
    # COMPATIBILITY
    # ========================================================

    async def process_message(
        self,
        message: Message,
        *,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        proactive_allowed: bool = True,
        activity_context: dict[str, Any] | None = None,
    ) -> ProcessedTelegramMessage:

        return await self.process(
            message,
            sara_called=sara_called,
            is_reply_to_sara=is_reply_to_sara,
            proactive_allowed=proactive_allowed,
            activity_context=activity_context,
        )

    # ========================================================
    # STATS
    # ========================================================

    def stats(self) -> dict[str, Any]:

        success_rate = 0.0

        if self._processed_messages:
            success_rate = (
                self._successful_messages
                / self._processed_messages
            )

        return {
            "processed_messages": (
                self._processed_messages
            ),
            "successful_messages": (
                self._successful_messages
            ),
            "failed_messages": (
                self._failed_messages
            ),
            "success_rate": round(
                success_rate,
                4,
            ),
        }

    def reset_stats(self) -> None:
        self._processed_messages = 0
        self._successful_messages = 0
        self._failed_messages = 0


# ============================================================
# GLOBAL INSTANCE
# ============================================================

group_agent = GroupAgent()


__all__ = [
    "GroupAgent",
    "group_agent",
        ]
