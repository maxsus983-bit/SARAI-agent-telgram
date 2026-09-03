from __future__ import annotations

import logging
import re
from typing import Any

from app.ai.context_builder import build_context
from app.ai.models import AIResponse
from app.ai.openrouter import OpenRouterError, openrouter
from app.ai.prompts import build_system_prompt
from app.config.settings import settings
from app.memory.auto_save import auto_save_memories


logger = logging.getLogger("sara.ai.engine")


class AIEngine:
    """
    SARA AI Engine.

    Vazifasi:

        Telegram message
              ↓
        Context Builder 2.0
              ↓
        Memory Retrieval 2.0
              ↓
        System Prompt
              ↓
        OpenRouter
              ↓
        AI Response
              ↓
        Memory Auto Save
    """

    # ==========================================================
    # INIT
    # ==========================================================

    def __init__(self) -> None:
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    # ==========================================================
    # SECURITY
    # ==========================================================

    _SECRET_PATTERNS = (
        re.compile(
            r"sk-[A-Za-z0-9_\-]{10,}",
            re.I,
        ),
        re.compile(
            r"sk-or-[A-Za-z0-9_\-]{10,}",
            re.I,
        ),
        re.compile(
            r"bot\d+:[A-Za-z0-9_\-]{20,}",
            re.I,
        ),
        re.compile(
            r"(api[_\- ]?key)\s*[:=]\s*\S+",
            re.I,
        ),
        re.compile(
            r"(password|passwd|parol)\s*[:=]\s*\S+",
            re.I,
        ),
        re.compile(
            r"(token)\s*[:=]\s*\S+",
            re.I,
        ),
    )

    @classmethod
    def _sanitize_context(cls, text: str) -> str:
        """
        Context ichidagi obvious secretlarni AI promptga yuborishdan
        oldin maskalaydi.

        Bu database memoryni o‘chirmaydi.
        Faqat AI request contextini himoya qiladi.
        """

        if not text:
            return ""

        result = str(text)

        for pattern in cls._SECRET_PATTERNS:
            result = pattern.sub(
                "[SECRET_REDACTED]",
                result,
            )

        return result

    # ==========================================================
    # GENERATE
    # ==========================================================

    async def generate(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        user_text: str,
        group_id: int | None = None,
        reply_to_message_id: int | None = None,
        is_group: bool = False,
        is_private: bool = False,
        is_bot_message: bool = False,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        is_question: bool = False,
        extra_flags: dict[str, Any] | None = None,
    ) -> AIResponse:

        self.total_requests += 1

        extra_flags = extra_flags or {}

        try:

            # ==================================================
            # 1. BUILD CONTEXT
            # ==================================================

            context = await build_context(
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,
                user_text=user_text,
                recent_messages=settings.max_recent_messages,
                memory_results=settings.max_memory_results,
            )

            conversation = self._sanitize_context(
                str(
                    context.get(
                        "conversation",
                        "",
                    )
                )
            )

            user_memory = self._sanitize_context(
                str(
                    context.get(
                        "user_memory",
                        "",
                    )
                )
            )

            group_memory = self._sanitize_context(
                str(
                    context.get(
                        "group_memory",
                        "",
                    )
                )
            )

            formatted_context = self._sanitize_context(
                str(
                    context.get(
                        "formatted_context",
                        "",
                    )
                )
            )

            # ==================================================
            # 2. AGENT FLAGS
            # ==================================================

            agent_context = {
                "chat_id": chat_id,
                "user_id": user_id,
                "group_id": group_id,
                "is_group": is_group,
                "is_private": is_private,
                "is_bot_message": is_bot_message,
                "sara_called": sara_called,
                "is_reply_to_sara": is_reply_to_sara,
                "is_question": is_question,
                "reply_to_message_id": reply_to_message_id,
                **extra_flags,
            }

            # ==================================================
            # 3. SYSTEM PROMPT
            # ==================================================

            system_prompt = build_system_prompt(
                is_group=is_group,
                is_private=is_private,
                user_id=user_id,
                group_id=group_id,
                agent_context=agent_context,
            )

            # ==================================================
            # 4. CONTEXT PROMPT
            # ==================================================

            context_prompt = self._build_context_prompt(
                conversation=conversation,
                user_memory=user_memory,
                group_memory=group_memory,
                formatted_context=formatted_context,
                is_group=is_group,
            )

            # ==================================================
            # 5. USER MESSAGE
            # ==================================================

            clean_user_text = self._sanitize_context(
                user_text
            ).strip()

            if not clean_user_text:
                clean_user_text = "(bo‘sh xabar)"

            # ==================================================
            # 6. OPENROUTER MESSAGES
            # ==================================================

            messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "system",
                    "content": context_prompt,
                },
                {
                    "role": "user",
                    "content": clean_user_text,
                },
            ]

            # ==================================================
            # 7. AI REQUEST
            # ==================================================

            logger.debug(
                "AI request | chat=%s | user=%s | group=%s",
                chat_id,
                user_id,
                group_id,
            )

            result = await openrouter.chat(
                messages=messages,
                temperature=0.7,
            )

            response_text = self._extract_response_text(
                result
            )

            if not response_text:
                raise RuntimeError(
                    "OpenRouter bo‘sh response qaytardi."
                )

            self.successful_requests += 1

            # ==================================================
            # 8. AUTO MEMORY SAVE
            # ==================================================

            if settings.memory_enabled:

                try:
                    await auto_save_memories(
                        user_telegram_id=user_id,
                        group_telegram_id=group_id,
                        text=user_text,
                    )

                except Exception:
                    # Memory save AI javobini buzmasligi kerak.
                    logger.exception(
                        "Memory auto-save failed | chat=%s",
                        chat_id,
                    )

            # ==================================================
            # 9. AI RESPONSE
            # ==================================================

            return AIResponse(
                text=response_text,
                model=getattr(
                    result,
                    "model",
                    None,
                ),
                usage=getattr(
                    result,
                    "usage",
                    None,
                ),
            )

        except OpenRouterError:
            self.failed_requests += 1

            logger.exception(
                "OpenRouter error | chat=%s",
                chat_id,
            )

            raise

        except Exception:
            self.failed_requests += 1

            logger.exception(
                "AI Engine failed | chat=%s",
                chat_id,
            )

            raise

    # ==========================================================
    # CONTEXT PROMPT
    # ==========================================================

    def _build_context_prompt(
        self,
        *,
        conversation: str,
        user_memory: str,
        group_memory: str,
        formatted_context: str,
        is_group: bool,
    ) -> str:
        """
        AI uchun contextni tartibli formatga keltiradi.
        """

        sections: list[str] = []

        sections.append(
            "SARA CONTEXT:"
        )

        sections.append(
            "\n[RECENT CONVERSATION]\n"
            + (
                conversation
                if conversation
                else "Mavjud emas."
            )
        )

        sections.append(
            "\n[USER MEMORY]\n"
            + (
                user_memory
                if user_memory
                else "Relevant memory topilmadi."
            )
        )

        if is_group:
            sections.append(
                "\n[GROUP MEMORY]\n"
                + (
                    group_memory
                    if group_memory
                    else "Relevant group memory topilmadi."
                )
            )

        # Agar formatted context mavjud bo‘lsa,
        # qo‘shimcha unified context sifatida ishlatamiz.
        if formatted_context:
            sections.append(
                "\n[UNIFIED CONTEXT]\n"
                + formatted_context
            )

        sections.append(
            """
MEMORY RULES:
- Contextdagi memory fakt sifatida berilgan, lekin ularni ko‘r-ko‘rona
  takrorlama.
- Agar memory userning oldingi gapiga tegishli bo‘lsa, tabiiy ravishda
  ishlat.
- Memory mavjud bo‘lmasa, o‘ylab topma.
- User haqida saqlangan ma'lumotni kerak bo‘lsa group contextda ham
  ishlatishing mumkin.
- API key, token, password yoki boshqa secretlarni hech qachon
  oshkor qilma.
- Eski conversation va memory bir-biriga zid bo‘lsa, eng yangi va
  ishonchli ma'lumotni afzal ko‘r.
"""
        )

        return "\n".join(sections)

    # ==========================================================
    # RESPONSE PARSER
    # ==========================================================

    @staticmethod
    def _extract_response_text(
        result: Any,
    ) -> str:

        if result is None:
            return ""

        # AIResponse
        if isinstance(result, AIResponse):
            return str(
                getattr(result, "text", "")
            ).strip()

        # OpenRouter response object
        if hasattr(result, "text"):
            return str(
                getattr(result, "text", "")
            ).strip()

        # Dictionary response
        if isinstance(result, dict):

            if "text" in result:
                return str(
                    result["text"]
                ).strip()

            if "content" in result:
                return str(
                    result["content"]
                ).strip()

            choices = result.get(
                "choices"
            )

            if choices:
                try:
                    content = (
                        choices[0]
                        .get("message", {})
                        .get("content", "")
                    )

                    if isinstance(
                        content,
                        list,
                    ):
                        parts = []

                        for item in content:
                            if isinstance(
                                item,
                                dict,
                            ):
                                if item.get(
                                    "type"
                                ) == "text":
                                    parts.append(
                                        str(
                                            item.get(
                                                "text",
                                                "",
                                            )
                                        )
                                    )

                        content = "\n".join(
                            parts
                        )

                    return str(
                        content
                    ).strip()

                except Exception:
                    return ""

        return str(result).strip()

    # ==========================================================
    # STATS
    # ==========================================================

    def stats(self) -> dict[str, int]:

        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
        }


# ==============================================================
# GLOBAL ENGINE
# ==============================================================

ai_engine = AIEngine()


__all__ = [
    "AIEngine",
    "ai_engine",
            ]
