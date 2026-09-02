from __future__ import annotations

from typing import Any

from app.ai.context_builder import build_context
from app.ai.openrouter import OpenRouterError, openrouter
from app.ai.prompts import build_system_prompt
from app.config.settings import settings


class AIEngine:

    async def generate(
        self,
        *,
        user_text: str,
        chat_id: int,
        user_id: int | None = None,
        group_id: int | None = None,
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

            return result.text

        except OpenRouterError:

            return (
                "Hozir AI server bilan bog‘lanishda "
                "muammo yuz berdi. Birozdan keyin yana urinib ko‘r."
            )


ai_engine = AIEngine()
