from __future__ import annotations

from app.memory.manager import memory_manager


async def retrieve_user_memory(
    user_telegram_id: int,
    limit: int = 15,
) -> str:

    return await memory_manager.build_user_memory_context(
        user_telegram_id=user_telegram_id,
        limit=limit,
    )


async def retrieve_group_memory(
    group_telegram_id: int,
    limit: int = 15,
) -> str:

    return await memory_manager.build_group_memory_context(
        group_telegram_id=group_telegram_id,
        limit=limit,
    )


async def retrieve_relevant_memory(
    user_telegram_id: int,
    query: str,
    limit: int = 15,
) -> str:

    memories = await memory_manager.search_user_memories(
        user_telegram_id=user_telegram_id,
        search_text=query,
        limit=limit,
    )

    if not memories:
        return "Bu mavzu bo'yicha saqlangan xotira topilmadi."

    return "\n".join(
        f"- [{memory.memory_type}] {memory.content}"
        for memory in memories
    )
