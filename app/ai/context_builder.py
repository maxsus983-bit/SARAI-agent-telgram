from __future__ import annotations

import re
from typing import Any

from app.config.settings import settings
from app.memory.conversation import build_conversation_context
from app.memory.retrieval import retrieve_relevant_memory


# ==============================================================
# CONTEXT BUILDER 2.0
# ==============================================================


def _clean_text(text: str | None) -> str:
    if not text:
        return ""

    return str(text).strip()


def _truncate(text: str, max_chars: int) -> str:
    text = _clean_text(text)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[context truncated]"


def _estimate_tokens(text: str) -> int:
    """
    Juda aniq tokenizer emas.
    Taxminiy context nazorati uchun.

    Odatda:
        1 token ≈ 4 character
    """

    if not text:
        return 0

    return max(
        1,
        len(text) // 4,
    )


def _extract_query(
    user_text: str | None,
) -> str:
    """
    User savolidan memory qidirish uchun query yaratadi.
    """

    text = _clean_text(user_text)

    if not text:
        return ""

    # Telegram mentionlarini olib tashlash.
    text = re.sub(
        r"@\w+",
        " ",
        text,
    )

    # Ortiqcha whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _format_section(
    title: str,
    content: str,
    empty_text: str,
) -> str:

    content = _clean_text(content)

    if not content:
        content = empty_text

    return (
        f"===== {title} =====\n"
        f"{content}"
    )


async def build_context(
    *,
    chat_id: int,
    user_id: int | None = None,
    group_id: int | None = None,
    user_text: str | None = None,
    recent_messages: int | None = None,
    memory_results: int | None = None,
) -> dict[str, Any]:
    """
    SARA AI uchun to‘liq context yaratadi.

    Context:

        1. Conversation
        2. User Memory
        3. Group Memory
        4. Query
        5. Metadata

    Group chatda user memory ham mavjud bo‘ladi.
    """

    recent_limit = (
        recent_messages
        if recent_messages is not None
        else settings.max_recent_messages
    )

    memory_limit = (
        memory_results
        if memory_results is not None
        else settings.max_memory_results
    )

    recent_limit = max(
        1,
        min(int(recent_limit), 200),
    )

    memory_limit = max(
        1,
        min(int(memory_limit), 100),
    )

    query = _extract_query(user_text)

    # ==========================================================
    # 1. CONVERSATION HISTORY
    # ==========================================================

    conversation = await build_conversation_context(
        chat_id=chat_id,
        limit=recent_limit,
    )

    conversation = _truncate(
        conversation,
        max_chars=24000,
    )

    # ==========================================================
    # 2. RELEVANT MEMORY
    # ==========================================================

    memory_data = await retrieve_relevant_memory(
        user_telegram_id=user_id,
        group_telegram_id=group_id,
        query=query,
        user_limit=memory_limit,
        group_limit=memory_limit,
    )

    user_memory = _clean_text(
        memory_data.get(
            "user_memory",
            "",
        )
    )

    group_memory = _clean_text(
        memory_data.get(
            "group_memory",
            "",
        )
    )

    user_memory = _truncate(
        user_memory,
        max_chars=12000,
    )

    group_memory = _truncate(
        group_memory,
        max_chars=12000,
    )

    # ==========================================================
    # 3. FORMAT CONTEXT
    # ==========================================================

    formatted_context_parts: list[str] = []

    formatted_context_parts.append(
        _format_section(
            "RECENT CONVERSATION",
            conversation,
            "Conversation history mavjud emas.",
        )
    )

    if user_id is not None:
        formatted_context_parts.append(
            _format_section(
                "USER MEMORY",
                user_memory,
                "User haqida relevant memory topilmadi.",
            )
        )

    if group_id is not None:
        formatted_context_parts.append(
            _format_section(
                "GROUP MEMORY",
                group_memory,
                "Guruh haqida relevant memory topilmadi.",
            )
        )

    formatted_context = "\n\n".join(
        formatted_context_parts
    )

    # ==========================================================
    # 4. TOKEN BUDGET
    # ==========================================================

    max_context_tokens = max(
        1000,
        int(settings.max_context_tokens),
    )

    estimated_tokens = _estimate_tokens(
        formatted_context
    )

    # Agar context haddan tashqari katta bo‘lsa,
    # conversationni qisqartiramiz.
    if estimated_tokens > max_context_tokens:

        allowed_chars = max_context_tokens * 4

        formatted_context = _truncate(
            formatted_context,
            max_chars=allowed_chars,
        )

        estimated_tokens = _estimate_tokens(
            formatted_context
        )

    # ==========================================================
    # 5. RETURN
    # ==========================================================

    return {
        "conversation": conversation,
        "user_memory": user_memory,
        "group_memory": group_memory,
        "query": query,
        "formatted_context": formatted_context,
        "estimated_tokens": estimated_tokens,
        "chat_id": chat_id,
        "user_id": user_id,
        "group_id": group_id,
        "memory_enabled": settings.memory_enabled,
    }


# ==============================================================
# SIMPLE CONTEXT
# ==============================================================


async def build_simple_context(
    *,
    chat_id: int,
    user_id: int | None = None,
    group_id: int | None = None,
    user_text: str | None = None,
) -> str:
    """
    Faqat tayyorlangan text context kerak bo‘lsa ishlatiladi.
    """

    context = await build_context(
        chat_id=chat_id,
        user_id=user_id,
        group_id=group_id,
        user_text=user_text,
    )

    return str(
        context.get(
            "formatted_context",
            "",
        )
    )


# ==============================================================
# MEMORY-ONLY CONTEXT
# ==============================================================


async def build_memory_context(
    *,
    user_id: int | None = None,
    group_id: int | None = None,
    query: str = "",
    limit: int = 15,
) -> dict[str, str]:
    """
    Conversation historysiz faqat memory olish.
    Agent Tool va Brain uchun qulay.
    """

    data = await retrieve_relevant_memory(
        user_telegram_id=user_id,
        group_telegram_id=group_id,
        query=query,
        user_limit=limit,
        group_limit=limit,
    )

    return {
        "user_memory": str(
            data.get(
                "user_memory",
                "",
            )
        ),
        "group_memory": str(
            data.get(
                "group_memory",
                "",
            )
        ),
    }


__all__ = [
    "build_context",
    "build_simple_context",
    "build_memory_context",
    ]
