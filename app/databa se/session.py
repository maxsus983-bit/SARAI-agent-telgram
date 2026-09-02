from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.settings import settings


def prepare_database_path() -> None:
    """
    SQLite ishlatilayotgan bo'lsa data papkasini yaratadi.
    PostgreSQL uchun hech narsa qilmaydi.
    """

    database_url = settings.database_url

    if database_url.startswith("sqlite"):
        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)


prepare_database_path()


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
)


SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """
    Database session yaratadi.
    """

    async with SessionFactory() as session:
        yield session


async def close_database() -> None:
    """
    Database connectionlarni yopadi.
    """

    await engine.dispose()
