from __future__ import annotations

from app.config.settings import settings
from app.memory.conversation import build_conversation_context
from app.memory.retrieval import (
    retrieve_group_memory,
    retrieve_user_memory,
)


async def build_context(
    *,
    chat_id: int,
    user_id: int | None = None,
    group_id: int | None = None,
    recent_messages: int | None = None,
    memory_results: int | None = None,
) -> dict[str, str]:

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

    # =========================================================
    # CONVERSATION MEMORY
    # =========================================================

    conversation = await build_conversation_context(
        chat_id=chat_id,
        limit=recent_limit,
    )

    # =========================================================
    # USER MEMORY
    # =========================================================

    if user_id is not None:

        user_memory = await retrieve_user_memory(
            user_telegram_id=user_id,
            limit=memory_limit,
        )

    else:

        user_memory = (
            "User ID mavjud emas. "
            "User memory topilmadi."
        )

    # =========================================================
    # GROUP MEMORY
    # =========================================================

    if group_id is not None:

        group_memory = await retrieve_group_memory(
            group_telegram_id=group_id,
            limit=memory_limit,
        )

    else:

        group_memory = (
            "Bu private chat. "
            "Group memory mavjud emas."
        )

    # =========================================================
    # FINAL CONTEXT
    # =========================================================
    #
    # Muhim o'zgarish:
    #
    # OLD:
    # GROUP → PRIVATE USER MEMORY HIDDEN
    #
    # NEW:
    # GROUP → USER MEMORY + GROUP MEMORY + CHAT HISTORY
    #
    # =========================================================

    return {
        "conversation": conversation,

        "user_memory": user_memory,

        "group_memory": group_memory,
    }
