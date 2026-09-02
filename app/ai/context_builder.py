from __future__ import annotations

from app.memory.conversation import build_conversation_context
from app.memory.retrieval import (
    retrieve_group_memory,
    retrieve_user_memory,
)


async def build_context(
    *,
    chat_id: int,
    user_id: int | None,
    group_id: int | None,
    recent_messages: int = 30,
    memory_results: int = 15,
) -> dict[str, str]:

    conversation = await build_conversation_context(
        chat_id=chat_id,
        limit=recent_messages,
    )

    user_memory = "N/A"

    if user_id is not None:
        user_memory = await retrieve_user_memory(
            user_telegram_id=user_id,
            limit=memory_results,
        )

    group_memory = "N/A"

    if group_id is not None:
        group_memory = await retrieve_group_memory(
            group_telegram_id=group_id,
            limit=memory_results,
        )

    return {
        "conversation": conversation,
        "user_memory": user_memory,
        "group_memory": group_memory,
      }
