from __future__ import annotations

from app.memory.extractor import ExtractedMemory
from app.memory.manager import memory_manager


async def save_extracted_user_memories(
    user_id: int,
    memories: list[ExtractedMemory],
    source_message_id: int | None = None,
) -> int:

    saved = 0

    for memory in memories:

        # GROUP_FACT shaxsiy xotiraga tushmasin.
        if memory.memory_type == "GROUP_FACT":
            continue

        await memory_manager.save_user_memory(
            user_telegram_id=user_id,
            content=memory.content,
            memory_type=memory.memory_type,
            importance=memory.importance,
            confidence=memory.confidence,
            source_message_id=source_message_id,
        )

        saved += 1

    return saved


async def save_extracted_group_memories(
    group_id: int,
    memories: list[ExtractedMemory],
    source_message_id: int | None = None,
) -> int:

    saved = 0

    for memory in memories:

        if memory.memory_type != "GROUP_FACT":
            continue

        await memory_manager.save_group_memory(
            group_telegram_id=group_id,
            content=memory.content,
            memory_type=memory.memory_type,
            importance=memory.importance,
            confidence=memory.confidence,
            source_message_id=source_message_id,
        )

        saved += 1

    return saved
