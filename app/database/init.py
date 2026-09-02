from sqlalchemy import text

from app.database.base import Base
from app.database.models import (
    User,
    Group,
    Conversation,
    Message,
    UserMemory,
    GroupMemory,
    Relationship,
    Reminder,
)
from app.database.session import engine


async def init_database() -> None:
    """
    SARA AI database jadvallarini yaratadi.

    Agar database yangi bo'lsa:
        users
        groups
        conversations
        messages
        user_memories
        group_memories
        relationships
        reminders

    avtomatik yaratiladi.
    """

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

        # SQLite foreign key nazorati.
        if connection.dialect.name == "sqlite":
            await connection.execute(
                text("PRAGMA foreign_keys = ON")
            )


async def check_database() -> bool:
    """
    Database ishlayotganini tekshiradi.
    """

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return True

    except Exception:
        return False
