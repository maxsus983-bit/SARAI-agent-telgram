from __future__ import annotations

from aiogram.types import Chat
from sqlalchemy import select

from app.database.models import Group
from app.database.session import SessionFactory


class GroupService:

    async def get_or_create(
        self,
        telegram_chat: Chat,
    ) -> Group:

        async with SessionFactory() as session:

            query = select(Group).where(
                Group.telegram_id == telegram_chat.id
            )

            result = await session.execute(query)
            group = result.scalar_one_or_none()

            if group is None:

                group = Group(
                    telegram_id=telegram_chat.id,
                    title=telegram_chat.title,
                    username=telegram_chat.username,
                )

                session.add(group)

            else:

                group.title = telegram_chat.title
                group.username = telegram_chat.username

            await session.commit()
            await session.refresh(group)

            return group


group_service = GroupService()
