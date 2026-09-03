from __future__ import annotations

from aiogram.types import User as TelegramUser
from sqlalchemy import select

from app.database.models import User
from app.database.session import SessionFactory


class UserService:
    """
    Telegram foydalanuvchisini DB bilan boshqaradi.

    Asosiy API:
        get_or_create(telegram_user)

    Compatibility API:
        get_or_create_user(...)
    """

    async def get_or_create(
        self,
        telegram_user: TelegramUser,
    ) -> User:

        async with SessionFactory() as session:

            result = await session.execute(
                select(User).where(
                    User.telegram_id == telegram_user.id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:

                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    language=telegram_user.language_code,
                    is_bot=telegram_user.is_bot,
                )

                session.add(user)

            else:

                user.username = telegram_user.username
                user.first_name = telegram_user.first_name
                user.last_name = telegram_user.last_name
                user.language = telegram_user.language_code
                user.is_bot = telegram_user.is_bot

            await session.commit()
            await session.refresh(user)

            return user

    async def get_or_create_user(
        self,
        *,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
        is_bot: bool = False,
    ) -> User:
        """
        private.py uchun compatibility API.

        Eski handler:
            get_or_create_user(...)

        yangi service:
            get_or_create(TelegramUser)
        """

        async with SessionFactory() as session:

            result = await session.execute(
                select(User).where(
                    User.telegram_id == telegram_id
                )
            )

            user = result.scalar_one_or_none()

            if user is None:

                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    language=language_code,
                    is_bot=is_bot,
                )

                session.add(user)

            else:

                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.language = language_code
                user.is_bot = is_bot

            await session.commit()
            await session.refresh(user)

            return user


user_service = UserService()


__all__ = [
    "UserService",
    "user_service",
]
