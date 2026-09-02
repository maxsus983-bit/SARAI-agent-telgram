from __future__ import annotations

from aiogram.types import User as TelegramUser
from sqlalchemy import select

from app.database.models import User
from app.database.session import SessionFactory


class UserService:

    async def get_or_create(
        self,
        telegram_user: TelegramUser,
    ) -> User:

        async with SessionFactory() as session:

            query = select(User).where(
                User.telegram_id == telegram_user.id
            )

            result = await session.execute(query)
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

                # Telegram'dagi o'zgarishlarni yangilaymiz.
                user.username = telegram_user.username
                user.first_name = telegram_user.first_name
                user.last_name = telegram_user.last_name
                user.language = telegram_user.language_code
                user.is_bot = telegram_user.is_bot

            await session.commit()
            await session.refresh(user)

            return user


user_service = UserService()
