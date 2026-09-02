from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.ai.context_builder import build_context
from app.ai.memory_extractor import memory_extractor
from app.ai.openrouter import OpenRouterError, openrouter
from app.ai.prompts import build_system_prompt
from app.config.settings import settings
from app.memory.auto_save import (
    save_extracted_group_memories,
    save_extracted_user_memories,
)


logger = logging.getLogger("sara.ai")


class AIEngine:

    async def generate(
        self,
        *,
        user_text: str,
        chat_id: int,
        user_id: int | None = None,
        group_id: int | None = None,
        source_message_id: int | None = None,
    ) -> str:

        context = await build_context(
            chat_id=chat_id,
            user_id=user_id,
            group_id=group_id,
            recent_messages=settings.max_recent_messages,
            memory_results=settings.max_memory_results,
        )

        system_prompt = build_system_prompt()

        context_message = f"""
RELEVANT CONTEXT
================

USER MEMORY:
{context["user_memory"]}

GROUP MEMORY:
{context["group_memory"]}

RECENT CONVERSATION:
{context["conversation"]}
""".strip()

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "system",
                "content": context_message,
            },
            {
                "role": "user",
                "content": user_text,
            },
        ]

        try:

            result = await openrouter.chat(
                messages=messages
            )

        except OpenRouterError:

            return (
                "Hozir AI server bilan bog‘lanishda "
                "muammo yuz berdi. Birozdan keyin yana urinib ko‘r."
            )

        # ------------------------------------------------------
        # MEMORY EXTRACTION
        # ------------------------------------------------------
        #
        # AI javobini kutdirib qo'ymaslik uchun
        # extraction alohida background task sifatida ishlaydi.
        #
        # Asosiy javob foydalanuvchiga tezroq ketadi.
        # ------------------------------------------------------

        if settings.memory_enabled:

            asyncio.create_task(
                self._extract_and_save_memory(
                    user_text=user_text,
                    conversation=context["conversation"],
                    user_id=user_id,
                    group_id=group_id,
                    source_message_id=source_message_id,
                )
            )

        return result.text

    async def _extract_and_save_memory(
        self,
        *,
        user_text: str,
        conversation: str,
        user_id: int | None,
        group_id: int | None,
        source_message_id: int | None,
    ) -> None:

        try:

            memories = await memory_extractor.extract(
                user_message=user_text,
                conversation_context=conversation,
            )

            if not memories:
                return

            if user_id is not None:

                await save_extracted_user_memories(
                    user_id=user_id,
                    memories=memories,
                    source_message_id=source_message_id,
                )

            if group_id is not None:

                await save_extracted_group_memories(
                    group_id=group_id,
                    memories=memories,
                    source_message_id=source_message_id,
                )

            logger.info(
                "Memory extraction: %s items",
                len(memories),
            )

        except Exception:

            logger.exception(
                "Unexpected memory extraction error."
            )


ai_engine = AIEngine()
