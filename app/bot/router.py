from __future__ import annotations

import logging

from aiogram import Router

from app.bot.handlers.commands import router as commands_router
from app.bot.handlers.private import router as private_router
from app.bot.handlers.groups import router as groups_router

logger = logging.getLogger("sara.bot.router")


router = Router(
    name="sara_main_router"
)


# ============================================================
# COMMANDS
# ============================================================

router.include_router(
    commands_router
)


# ============================================================
# PRIVATE
# ============================================================

router.include_router(
    private_router
)


# ============================================================
# GROUPS
# ============================================================

router.include_router(
    groups_router
)


logger.info(
    "SARA Telegram routers loaded successfully."
)


__all__ = [
    "router",
]
