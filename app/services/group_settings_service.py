from __future__ import annotations

import logging

from sqlalchemy import select

from app.database.models import Group
from app.database.session import SessionFactory

logger = logging.getLogger("sara.services.group_settings")


class GroupSettingsService:
    """
    SARA guruh sozlamalarini boshqaradi.

    Barcha o'zgarishlar SQLite/PostgreSQL database'da saqlanadi.
    Bot restart bo'lgandan keyin ham sozlamalar yo'qolmaydi.
    """

    async def get(self, group_id: int) -> Group | None:
        async with SessionFactory() as session:
            result = await session.execute(
                select(Group).where(
                    Group.telegram_id == group_id
                )
            )

            return result.scalar_one_or_none()

    async def ensure(self, group_id: int, title: str | None = None) -> Group:
        async with SessionFactory() as session:
            result = await session.execute(
                select(Group).where(
                    Group.telegram_id == group_id
                )
            )

            group = result.scalar_one_or_none()

            if group is None:
                group = Group(
                    telegram_id=group_id,
                    title=title,
                    enabled=True,
                    proactive_enabled=True,
                    quiet_mode=False,
                )

                session.add(group)
                await session.commit()
                await session.refresh(group)

                return group

            changed = False

            if title and group.title != title:
                group.title = title
                changed = True

            if changed:
                await session.commit()
                await session.refresh(group)

            return group

    async def set_enabled(
        self,
        *,
        group_id: int,
        enabled: bool,
        title: str | None = None,
    ) -> Group:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        async with SessionFactory() as session:
            result = await session.execute(
                select(Group).where(
                    Group.telegram_id == group_id
                )
            )

            group = result.scalar_one()

            group.enabled = enabled

            await session.commit()
            await session.refresh(group)

            return group

    async def set_proactive(
        self,
        *,
        group_id: int,
        enabled: bool,
        title: str | None = None,
    ) -> Group:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        async with SessionFactory() as session:
            result = await session.execute(
                select(Group).where(
                    Group.telegram_id == group_id
                )
            )

            group = result.scalar_one()

            group.proactive_enabled = enabled

            await session.commit()
            await session.refresh(group)

            return group

    async def set_quiet_mode(
        self,
        *,
        group_id: int,
        enabled: bool,
        title: str | None = None,
    ) -> Group:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        async with SessionFactory() as session:
            result = await session.execute(
                select(Group).where(
                    Group.telegram_id == group_id
                )
            )

            group = result.scalar_one()

            group.quiet_mode = enabled

            await session.commit()
            await session.refresh(group)

            return group

    async def toggle_enabled(
        self,
        *,
        group_id: int,
        title: str | None = None,
    ) -> Group:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        return await self.set_enabled(
            group_id=group_id,
            enabled=not group.enabled,
            title=title,
        )

    async def toggle_proactive(
        self,
        *,
        group_id: int,
        title: str | None = None,
    ) -> Group:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        return await self.set_proactive(
            group_id=group_id,
            enabled=not group.proactive_enabled,
            title=title,
        )

    async def toggle_quiet_mode(
        self,
        *,
        group_id: int,
        title: str | None = None,
    ) -> Group:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        return await self.set_quiet_mode(
            group_id=group_id,
            enabled=not group.quiet_mode,
            title=title,
        )

    async def settings_text(
        self,
        *,
        group_id: int,
        title: str | None = None,
    ) -> str:
        group = await self.ensure(
            group_id=group_id,
            title=title,
        )

        return (
            "⚙️ <b>SARA GROUP SETTINGS</b>\n\n"
            f"👥 Guruh: <b>{group.title or 'Nomaʼlum'}</b>\n\n"
            f"🤖 SARA: "
            f"<b>{'ON 🟢' if group.enabled else 'OFF 🔴'}</b>\n"
            f"🧠 Proactive AI: "
            f"<b>{'ON 🟢' if group.proactive_enabled else 'OFF 🔴'}</b>\n"
            f"🤫 Quiet mode: "
            f"<b>{'ON 🟢' if group.quiet_mode else 'OFF 🔴'}</b>\n\n"
            "Admin commandlar:\n"
            "<code>/sara_enable</code>\n"
            "<code>/sara_disable</code>\n"
            "<code>/proactive on</code>\n"
            "<code>/proactive off</code>\n"
            "<code>/quiet on</code>\n"
            "<code>/quiet off</code>"
        )


group_settings_service = GroupSettingsService()
