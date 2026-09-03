from __future__ import annotations

import logging
from typing import Any

from app.memory.manager import memory_manager

logger = logging.getLogger("sara.agent.tools.memory")


class MemoryTool:
    """
    SARA Memory Tool.

    Vazifalari:
    - User memory saqlash
    - Group memory saqlash
    - User memory qidirish
    - Group memory qidirish
    - Memory o'chirish
    - Memory sonini ko'rish

    Eslatma:
    Oddiy chat xabarlari ham conversation history orqali
    alohida saqlanadi. Bu tool esa agentga uzoq muddatli
    memory bilan ishlash imkonini beradi.
    """

    async def save_user_memory(
        self,
        *,
        user_telegram_id: int,
        content: str,
        memory_type: str = "IMPORTANT_FACT",
        importance: float = 0.8,
        confidence: float = 0.95,
        source_message_id: int | None = None,
    ) -> dict[str, Any]:
        content = str(content).strip()

        if not content:
            return {
                "success": False,
                "error": "empty_memory",
            }

        try:
            memory = await memory_manager.save_user_memory(
                user_telegram_id=user_telegram_id,
                memory_type=memory_type,
                content=content,
                importance=importance,
                confidence=confidence,
                source_message_id=source_message_id,
            )

            return {
                "success": True,
                "memory_id": getattr(memory, "id", None),
                "user_telegram_id": user_telegram_id,
                "memory_type": memory_type,
                "content": content,
            }

        except Exception as exc:
            logger.exception(
                "Failed to save user memory | user=%s",
                user_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
            }

    async def save_group_memory(
        self,
        *,
        group_telegram_id: int,
        content: str,
        memory_type: str = "GROUP_FACT",
        importance: float = 0.8,
        confidence: float = 0.95,
        source_message_id: int | None = None,
    ) -> dict[str, Any]:
        content = str(content).strip()

        if not content:
            return {
                "success": False,
                "error": "empty_memory",
            }

        try:
            memory = await memory_manager.save_group_memory(
                group_telegram_id=group_telegram_id,
                memory_type=memory_type,
                content=content,
                importance=importance,
                confidence=confidence,
                source_message_id=source_message_id,
            )

            return {
                "success": True,
                "memory_id": getattr(memory, "id", None),
                "group_telegram_id": group_telegram_id,
                "memory_type": memory_type,
                "content": content,
            }

        except Exception as exc:
            logger.exception(
                "Failed to save group memory | group=%s",
                group_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
            }

    async def search_user_memory(
        self,
        *,
        user_telegram_id: int,
        query: str,
        limit: int = 15,
    ) -> dict[str, Any]:
        query = str(query).strip()

        if not query:
            return {
                "success": False,
                "error": "empty_query",
                "memories": [],
            }

        try:
            memories = await memory_manager.search_user_memory(
                user_telegram_id=user_telegram_id,
                query=query,
                limit=limit,
            )

            return {
                "success": True,
                "user_telegram_id": user_telegram_id,
                "query": query,
                "count": len(memories),
                "memories": [
                    self._serialize_memory(memory)
                    for memory in memories
                ],
            }

        except Exception as exc:
            logger.exception(
                "Failed to search user memory | user=%s",
                user_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
                "memories": [],
            }

    async def search_group_memory(
        self,
        *,
        group_telegram_id: int,
        query: str,
        limit: int = 15,
    ) -> dict[str, Any]:
        query = str(query).strip()

        if not query:
            return {
                "success": False,
                "error": "empty_query",
                "memories": [],
            }

        try:
            memories = await memory_manager.search_group_memory(
                group_telegram_id=group_telegram_id,
                query=query,
                limit=limit,
            )

            return {
                "success": True,
                "group_telegram_id": group_telegram_id,
                "query": query,
                "count": len(memories),
                "memories": [
                    self._serialize_memory(memory)
                    for memory in memories
                ],
            }

        except Exception as exc:
            logger.exception(
                "Failed to search group memory | group=%s",
                group_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
                "memories": [],
            }

    async def get_user_memories(
        self,
        *,
        user_telegram_id: int,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            memories = await memory_manager.get_user_memories(
                user_telegram_id=user_telegram_id,
                limit=limit,
            )

            return {
                "success": True,
                "user_telegram_id": user_telegram_id,
                "count": len(memories),
                "memories": [
                    self._serialize_memory(memory)
                    for memory in memories
                ],
            }

        except Exception as exc:
            logger.exception(
                "Failed to get user memories | user=%s",
                user_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
                "memories": [],
            }

    async def get_group_memories(
        self,
        *,
        group_telegram_id: int,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            memories = await memory_manager.get_group_memories(
                group_telegram_id=group_telegram_id,
                limit=limit,
            )

            return {
                "success": True,
                "group_telegram_id": group_telegram_id,
                "count": len(memories),
                "memories": [
                    self._serialize_memory(memory)
                    for memory in memories
                ],
            }

        except Exception as exc:
            logger.exception(
                "Failed to get group memories | group=%s",
                group_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
                "memories": [],
            }

    async def forget_user_memory(
        self,
        *,
        user_telegram_id: int,
        memory_id: int,
    ) -> dict[str, Any]:
        try:
            result = await memory_manager.forget_user_memory(
                user_telegram_id=user_telegram_id,
                memory_id=memory_id,
            )

            return {
                "success": bool(result),
                "memory_id": memory_id,
                "user_telegram_id": user_telegram_id,
            }

        except Exception as exc:
            logger.exception(
                "Failed to forget user memory | user=%s memory=%s",
                user_telegram_id,
                memory_id,
            )

            return {
                "success": False,
                "error": str(exc),
            }

    async def forget_group_memory(
        self,
        *,
        group_telegram_id: int,
        memory_id: int,
    ) -> dict[str, Any]:
        try:
            result = await memory_manager.forget_group_memory(
                group_telegram_id=group_telegram_id,
                memory_id=memory_id,
            )

            return {
                "success": bool(result),
                "memory_id": memory_id,
                "group_telegram_id": group_telegram_id,
            }

        except Exception as exc:
            logger.exception(
                "Failed to forget group memory | group=%s memory=%s",
                group_telegram_id,
                memory_id,
            )

            return {
                "success": False,
                "error": str(exc),
            }

    async def count_user_memory(
        self,
        *,
        user_telegram_id: int,
    ) -> dict[str, Any]:
        try:
            count = await memory_manager.count_user_memory(
                user_telegram_id=user_telegram_id,
            )

            return {
                "success": True,
                "user_telegram_id": user_telegram_id,
                "count": count,
            }

        except Exception as exc:
            logger.exception(
                "Failed to count user memory | user=%s",
                user_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
            }

    async def count_group_memory(
        self,
        *,
        group_telegram_id: int,
    ) -> dict[str, Any]:
        try:
            count = await memory_manager.count_group_memory(
                group_telegram_id=group_telegram_id,
            )

            return {
                "success": True,
                "group_telegram_id": group_telegram_id,
                "count": count,
            }

        except Exception as exc:
            logger.exception(
                "Failed to count group memory | group=%s",
                group_telegram_id,
            )

            return {
                "success": False,
                "error": str(exc),
            }

    @staticmethod
    def _serialize_memory(memory: Any) -> dict[str, Any]:
        return {
            "id": getattr(memory, "id", None),
            "memory_type": getattr(memory, "memory_type", None),
            "content": getattr(memory, "content", ""),
            "importance": getattr(memory, "importance", None),
            "confidence": getattr(memory, "confidence", None),
            "source_message_id": getattr(
                memory,
                "source_message_id",
                None,
            ),
            "active": getattr(memory, "active", True),
            "created_at": (
                getattr(memory, "created_at", None).isoformat()
                if getattr(memory, "created_at", None)
                else None
            ),
        }


memory_tool = MemoryTool()


async def memory_tool_handler(
    *,
    operation: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Tool Registry uchun yagona entry point.

    operation:
        save_user
        save_group
        search_user
        search_group
        get_user
        get_group
        forget_user
        forget_group
        count_user
        count_group
    """

    operations = {
        "save_user": memory_tool.save_user_memory,
        "save_group": memory_tool.save_group_memory,
        "search_user": memory_tool.search_user_memory,
        "search_group": memory_tool.search_group_memory,
        "get_user": memory_tool.get_user_memories,
        "get_group": memory_tool.get_group_memories,
        "forget_user": memory_tool.forget_user_memory,
        "forget_group": memory_tool.forget_group_memory,
        "count_user": memory_tool.count_user_memory,
        "count_group": memory_tool.count_group_memory,
    }

    handler = operations.get(operation)

    if handler is None:
        return {
            "success": False,
            "error": f"unknown_memory_operation:{operation}",
        }

    try:
        return await handler(**kwargs)
    except Exception as exc:
        logger.exception(
            "Memory tool operation failed | operation=%s",
            operation,
        )

        return {
            "success": False,
            "error": str(exc),
          }
