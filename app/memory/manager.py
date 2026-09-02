from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, func, or_, select

from app.database.models import GroupMemory, UserMemory
from app.database.session import SessionFactory


class MemoryManager:
    """
    SARA AI doimiy xotirasini boshqaradi.

    Xotira database'da saqlanadi.
    Bot restart bo'lsa ham ma'lumotlar qoladi.
    """

    # ==========================================================
    # USER MEMORY
    # ==========================================================

    async def save_user_memory(
        self,
        user_telegram_id: int,
        content: str,
        memory_type: str = "IMPORTANT_FACT",
        importance: int = 50,
        confidence: float = 1.0,
        source_message_id: Optional[int] = None,
    ) -> UserMemory:

        importance = max(0, min(100, importance))
        confidence = max(0.0, min(1.0, confidence))

        async with SessionFactory() as session:

            # Bir xil xotirani qayta-qayta saqlamaslik.
            existing_query = select(UserMemory).where(
                UserMemory.user_telegram_id == user_telegram_id,
                UserMemory.content == content,
                UserMemory.active.is_(True),
            )

            result = await session.execute(existing_query)
            existing = result.scalar_one_or_none()

            if existing:
                existing.importance = max(
                    existing.importance,
                    importance,
                )

                existing.confidence = max(
                    existing.confidence,
                    confidence,
                )

                await session.commit()
                await session.refresh(existing)

                return existing

            memory = UserMemory(
                user_telegram_id=user_telegram_id,
                memory_type=memory_type,
                content=content,
                importance=importance,
                confidence=confidence,
                source_message_id=source_message_id,
                active=True,
            )

            session.add(memory)

            await session.commit()
            await session.refresh(memory)

            return memory

    async def get_user_memories(
        self,
        user_telegram_id: int,
        limit: int = 15,
    ) -> list[UserMemory]:

        limit = max(1, min(limit, 100))

        async with SessionFactory() as session:

            query = (
                select(UserMemory)
                .where(
                    UserMemory.user_telegram_id == user_telegram_id,
                    UserMemory.active.is_(True),
                )
                .order_by(
                    UserMemory.importance.desc(),
                    UserMemory.updated_at.desc(),
                )
                .limit(limit)
            )

            result = await session.execute(query)

            return list(result.scalars().all())

    async def search_user_memories(
        self,
        user_telegram_id: int,
        search_text: str,
        limit: int = 15,
    ) -> list[UserMemory]:

        limit = max(1, min(limit, 100))

        search_pattern = f"%{search_text}%"

        async with SessionFactory() as session:

            query = (
                select(UserMemory)
                .where(
                    UserMemory.user_telegram_id == user_telegram_id,
                    UserMemory.active.is_(True),
                    or_(
                        UserMemory.content.ilike(search_pattern),
                        UserMemory.memory_type.ilike(search_pattern),
                    ),
                )
                .order_by(
                    UserMemory.importance.desc(),
                    UserMemory.updated_at.desc(),
                )
                .limit(limit)
            )

            result = await session.execute(query)

            return list(result.scalars().all())

    async def forget_user_memory(
        self,
        user_telegram_id: int,
        memory_id: int,
    ) -> bool:

        async with SessionFactory() as session:

            query = select(UserMemory).where(
                UserMemory.id == memory_id,
                UserMemory.user_telegram_id == user_telegram_id,
                UserMemory.active.is_(True),
            )

            result = await session.execute(query)
            memory = result.scalar_one_or_none()

            if not memory:
                return False

            memory.active = False

            await session.commit()

            return True

    async def clear_user_memories(
        self,
        user_telegram_id: int,
    ) -> int:

        async with SessionFactory() as session:

            query = delete(UserMemory).where(
                UserMemory.user_telegram_id == user_telegram_id
            )

            result = await session.execute(query)

            await session.commit()

            return result.rowcount or 0

    async def user_memory_count(
        self,
        user_telegram_id: int,
    ) -> int:

        async with SessionFactory() as session:

            query = select(
                func.count(UserMemory.id)
            ).where(
                UserMemory.user_telegram_id == user_telegram_id,
                UserMemory.active.is_(True),
            )

            result = await session.execute(query)

            return int(result.scalar_one())

    # ==========================================================
    # GROUP MEMORY
    # ==========================================================

    async def save_group_memory(
        self,
        group_telegram_id: int,
        content: str,
        memory_type: str = "GROUP_FACT",
        importance: int = 50,
        confidence: float = 1.0,
        source_message_id: Optional[int] = None,
    ) -> GroupMemory:

        importance = max(0, min(100, importance))
        confidence = max(0.0, min(1.0, confidence))

        async with SessionFactory() as session:

            existing_query = select(GroupMemory).where(
                GroupMemory.group_telegram_id == group_telegram_id,
                GroupMemory.content == content,
                GroupMemory.active.is_(True),
            )

            result = await session.execute(existing_query)
            existing = result.scalar_one_or_none()

            if existing:

                existing.importance = max(
                    existing.importance,
                    importance,
                )

                existing.confidence = max(
                    existing.confidence,
                    confidence,
                )

                await session.commit()
                await session.refresh(existing)

                return existing

            memory = GroupMemory(
                group_telegram_id=group_telegram_id,
                memory_type=memory_type,
                content=content,
                importance=importance,
                confidence=confidence,
                source_message_id=source_message_id,
                active=True,
            )

            session.add(memory)

            await session.commit()
            await session.refresh(memory)

            return memory

    async def get_group_memories(
        self,
        group_telegram_id: int,
        limit: int = 15,
    ) -> list[GroupMemory]:

        limit = max(1, min(limit, 100))

        async with SessionFactory() as session:

            query = (
                select(GroupMemory)
                .where(
                    GroupMemory.group_telegram_id == group_telegram_id,
                    GroupMemory.active.is_(True),
                )
                .order_by(
                    GroupMemory.importance.desc(),
                    GroupMemory.updated_at.desc(),
                )
                .limit(limit)
            )

            result = await session.execute(query)

            return list(result.scalars().all())

    async def search_group_memories(
        self,
        group_telegram_id: int,
        search_text: str,
        limit: int = 15,
    ) -> list[GroupMemory]:

        limit = max(1, min(limit, 100))

        search_pattern = f"%{search_text}%"

        async with SessionFactory() as session:

            query = (
                select(GroupMemory)
                .where(
                    GroupMemory.group_telegram_id == group_telegram_id,
                    GroupMemory.active.is_(True),
                    or_(
                        GroupMemory.content.ilike(search_pattern),
                        GroupMemory.memory_type.ilike(search_pattern),
                    ),
                )
                .order_by(
                    GroupMemory.importance.desc(),
                    GroupMemory.updated_at.desc(),
                )
                .limit(limit)
            )

            result = await session.execute(query)

            return list(result.scalars().all())

    async def clear_group_memories(
        self,
        group_telegram_id: int,
    ) -> int:

        async with SessionFactory() as session:

            query = delete(GroupMemory).where(
                GroupMemory.group_telegram_id == group_telegram_id
            )

            result = await session.execute(query)

            await session.commit()

            return result.rowcount or 0

    # ==========================================================
    # CONTEXT BUILDER
    # ==========================================================

    async def build_user_memory_context(
        self,
        user_telegram_id: int,
        limit: int = 15,
    ) -> str:

        memories = await self.get_user_memories(
            user_telegram_id,
            limit,
        )

        if not memories:
            return "User haqida saqlangan xotira mavjud emas."

        lines = []

        for memory in memories:
            lines.append(
                f"- [{memory.memory_type}] "
                f"{memory.content} "
                f"(importance={memory.importance}, "
                f"confidence={memory.confidence:.2f})"
            )

        return "\n".join(lines)

    async def build_group_memory_context(
        self,
        group_telegram_id: int,
        limit: int = 15,
    ) -> str:

        memories = await self.get_group_memories(
            group_telegram_id,
            limit,
        )

        if not memories:
            return "Guruh haqida saqlangan xotira mavjud emas."

        lines = []

        for memory in memories:
            lines.append(
                f"- [{memory.memory_type}] "
                f"{memory.content} "
                f"(importance={memory.importance}, "
                f"confidence={memory.confidence:.2f})"
            )

        return "\n".join(lines)


memory_manager = MemoryManager()
