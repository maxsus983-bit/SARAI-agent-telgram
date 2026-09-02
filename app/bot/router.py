from aiogram import Router

from app.bot.handlers.commands import router as commands_router
from app.bot.handlers.private import router as private_router
from app.bot.handlers.groups import router as groups_router
from app.bot.handlers.media import router as media_router


def create_router() -> Router:
    router = Router()

    router.include_router(commands_router)
    router.include_router(media_router)
    router.include_router(private_router)
    router.include_router(groups_router)

    return router
