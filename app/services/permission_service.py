from __future__ import annotations

from aiogram.types import Message

from app.config.settings import settings


class PermissionService:

    def get_admin_ids(self) -> set[int]:
        result: set[int] = set()

        if not settings.admin_ids:
            return result

        for item in settings.admin_ids.split(","):
            item = item.strip()

            if not item:
                continue

            try:
                result.add(int(item))
            except ValueError:
                continue

        return result

    def is_admin(
        self,
        user_id: int,
    ) -> bool:

        return user_id in self.get_admin_ids()

    def is_group(
        self,
        message: Message,
    ) -> bool:

        return message.chat.type in {
            "group",
            "supergroup",
        }

    def is_private(
        self,
        message: Message,
    ) -> bool:

        return message.chat.type == "private"

    def can_manage_group(
        self,
        message: Message,
    ) -> bool:

        if not message.from_user:
            return False

        return self.is_admin(
            message.from_user.id
        )

    async def is_telegram_admin(
        self,
        message: Message,
    ) -> bool:

        if not self.is_group(message):
            return False

        if not message.from_user:
            return False

        try:
            member = await message.bot.get_chat_member(
                chat_id=message.chat.id,
                user_id=message.from_user.id,
            )

            return member.status in {
                "administrator",
                "creator",
            }

        except Exception:
            return False

    async def can_manage_group_async(
        self,
        message: Message,
    ) -> bool:

        if not message.from_user:
            return False

        if self.is_admin(
            message.from_user.id
        ):
            return True

        return await self.is_telegram_admin(
            message
        )


permission_service = PermissionService()
