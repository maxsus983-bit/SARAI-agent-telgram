"""
SARA AI Telegram Router.

Barcha Telegram handler routerlarini bitta
asosiy Router orqali birlashtiradi.
"""

from __future__ import annotations

import logging

from aiogram import Router

from app.bot.handlers.commands import router as commands_router
from app.bot.handlers.private import router as private_router

logger = logging.getLogger("sara.bot.router")


# ============================================================
# MAIN ROUTER
# ============================================================

router = Router(name="sara_main_router")


# ============================================================
# CHILD ROUTERS
# ============================================================

# Buyruqlar:
# /start
# /help
# /memory
# /forget
# /remind
# va boshqalar.
router.include_router(commands_router)


# Private chatlar:
# oddiy AI suhbatlari,
# memory,
# agent,
# OpenRouter va boshqalar.
router.include_router(private_router)


logger.info(
    "SARA Telegram routers loaded successfully."
)


__all__ = ["router"]
