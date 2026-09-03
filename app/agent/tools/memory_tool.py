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
      - Memory qidirish
      - Memory olish
      - Memory o'chirish
      - Memory tiklash
      - Memory sonini olish

    Muhim:
      - API key / token / password kabi secretlar MemoryManager
        tomonidan saqlanmaydi.
      - User memory guruh kontekstida ishlatilishi mumkin.
      - Har bir userning memory'si telegram user ID bilan ajratiladi.
      - Har bir group memory'si telegram group ID bilan ajratiladi.
    """

    def __init__(self) -> None:
        self.manager = memory_manager

    # ============================================================
    # USER MEMORY
    # ============================================================

    async def save_user(
        self,
        *,
        user_telegram_id: int,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        confidence: float = 0.8,
        source_message_id: int | None = None,
    ) -> dict[str, Any]:

        result = await self.manager.save_user_memory(
            user_telegram_id=int(user_telegram_id),
            memory_type=str(memory_type),
            content=str(content),
            importance=float(importance),
            confidence=float(confidence),
            source_message_id=source_message_id,
        )

        return {
            "success": bool(result),
            "type": "user_memory",
            "memory": result,
        }

    async def search_user(
        self,
        *,
        user_telegram_id: int,
        query: str = "",
        limit: int = 10,
    ) -> dict[str, Any]:

        memories = await self.manager.search_user_memory(
            user_telegram_id=int(user_telegram_id),
            query=str(query or ""),
            limit=int(limit),
        )

        return {
            "success": True,
            "type": "user_memory_search",
            "count": len(memories),
            "memories": memories,
        }

    async def get_user(
        self,
        *,
        user_telegram_id: int,
        limit: int = 15,
        include_inactive: bool = False,
    ) -> dict[str, Any]:

        memories = await self.manager.get_user_memories(
            user_telegram_id=int(user_telegram_id),
            limit=int(limit),
            include_inactive=bool(include_inactive),
        )

        return {
            "success": True,
            "type": "user_memory",
            "count": len(memories),
            "memories": memories,
        }

    async def forget_user(
        self,
        *,
        memory_id: int,
    ) -> dict[str, Any]:

        result = await self.manager.forget_user_memory(
            int(memory_id)
        )

        return {
            "success": bool(result),
            "type": "user_memory_forget",
            "memory_id": int(memory_id),
        }

    async def restore_user(
        self,
        *,
        memory_id: int,
    ) -> dict[str, Any]:

        result = await self.manager.restore_user_memory(
            int(memory_id)
        )

        return {
            "success": bool(result),
            "type": "user_memory_restore",
            "memory_id": int(memory_id),
        }

    async def count_user(
        self,
        *,
        user_telegram_id: int,
    ) -> dict[str, Any]:

        count = await self.manager.user_memory_count(
            int(user_telegram_id)
        )

        return {
            "success": True,
            "type": "user_memory_count",
            "count": int(count),
        }

    # ============================================================
    # GROUP MEMORY
    # ============================================================

    async def save_group(
        self,
        *,
        group_telegram_id: int,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        confidence: float = 0.8,
        source_message_id: int | None = None,
    ) -> dict[str, Any]:

        result = await self.manager.save_group_memory(
            group_telegram_id=int(group_telegram_id),
            memory_type=str(memory_type),
            content=str(content),
            importance=float(importance),
            confidence=float(confidence),
            source_message_id=source_message_id,
        )

        return {
            "success": bool(result),
            "type": "group_memory",
            "memory": result,
        }

    async def search_group(
        self,
        *,
        group_telegram_id: int,
        query: str = "",
        limit: int = 10,
    ) -> dict[str, Any]:

        memories = await self.manager.search_group_memory(
            group_telegram_id=int(group_telegram_id),
            query=str(query or ""),
            limit=int(limit),
        )

        return {
            "success": True,
            "type": "group_memory_search",
            "count": len(memories),
            "memories": memories,
        }

    async def get_group(
        self,
        *,
        group_telegram_id: int,
        limit: int = 15,
        include_inactive: bool = False,
    ) -> dict[str, Any]:

        memories = await self.manager.get_group_memories(
            group_telegram_id=int(group_telegram_id),
            limit=int(limit),
            include_inactive=bool(include_inactive),
        )

        return {
            "success": True,
            "type": "group_memory",
            "count": len(memories),
            "memories": memories,
        }

    async def forget_group(
        self,
        *,
        memory_id: int,
    ) -> dict[str, Any]:

        result = await self.manager.forget_group_memory(
            int(memory_id)
        )

        return {
            "success": bool(result),
            "type": "group_memory_forget",
            "memory_id": int(memory_id),
        }

    async def restore_group(
        self,
        *,
        memory_id: int,
    ) -> dict[str, Any]:

        result = await self.manager.restore_group_memory(
            int(memory_id)
        )

        return {
            "success": bool(result),
            "type": "group_memory_restore",
            "memory_id": int(memory_id),
        }

    async def count_group(
        self,
        *,
        group_telegram_id: int,
    ) -> dict[str, Any]:

        count = await self.manager.group_memory_count(
            int(group_telegram_id)
        )

        return {
            "success": True,
            "type": "group_memory_count",
            "count": int(count),
        }


# ================================================================
# GLOBAL TOOL
# ================================================================

memory_tool = MemoryTool()


# ================================================================
# TOOL HANDLER
# ================================================================

async def memory_tool_handler(
    operation: str,
    **kwargs: Any,
) -> dict[str, Any]:

    operation = str(operation or "").strip().lower()

    try:

        # --------------------------------------------------------
        # USER
        # --------------------------------------------------------

        if operation == "save_user":
            return await memory_tool.save_user(**kwargs)

        if operation in {
            "search_user",
            "search_user_memory",
        }:
            return await memory_tool.search_user(**kwargs)

        if operation in {
            "get_user",
            "get_user_memory",
        }:
            return await memory_tool.get_user(**kwargs)

        if operation in {
            "forget_user",
            "forget_user_memory",
        }:
            return await memory_tool.forget_user(**kwargs)

        if operation in {
            "restore_user",
            "restore_user_memory",
        }:
            return await memory_tool.restore_user(**kwargs)

        if operation in {
            "count_user",
            "count_user_memory",
        }:
            return await memory_tool.count_user(**kwargs)

        # --------------------------------------------------------
        # GROUP
        # --------------------------------------------------------

        if operation == "save_group":
            return await memory_tool.save_group(**kwargs)

        if operation in {
            "search_group",
            "search_group_memory",
        }:
            return await memory_tool.search_group(**kwargs)

        if operation in {
            "get_group",
            "get_group_memory",
        }:
            return await memory_tool.get_group(**kwargs)

        if operation in {
            "forget_group",
            "forget_group_memory",
        }:
            return await memory_tool.forget_group(**kwargs)

        if operation in {
            "restore_group",
            "restore_group_memory",
        }:
            return await memory_tool.restore_group(**kwargs)

        if operation in {
            "count_group",
            "count_group_memory",
        }:
            return await memory_tool.count_group(**kwargs)

        return {
            "success": False,
            "error": f"unknown_memory_operation:{operation}",
        }

    except Exception as exc:
        logger.exception(
            "Memory Tool failed | operation=%s",
            operation,
        )

        return {
            "success": False,
            "operation": operation,
            "error": str(exc),
        }


__all__ = [
    "MemoryTool",
    "memory_tool",
    "memory_tool_handler",
        ]
