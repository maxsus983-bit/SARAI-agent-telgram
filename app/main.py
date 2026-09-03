from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from app.agent.tools.memory_tool import memory_tool_handler
from app.agent.tools.reminder_tool import reminder_tool_handler

from app.agent.tools.telegram_tool import (
    configure_telegram_tool,
    send_telegram_message,
)

from app.agent.tool_registry import tool_registry

from app.bot.router import create_router

from app.config.settings import settings

from app.database.init import init_database
from app.database.session import close_database

from app.scheduler.manager import scheduler_manager
from app.scheduler.recovery import restore_reminders


# ================================================================
# LOGGING
# ================================================================

logging.basicConfig(
    level=getattr(
        logging,
        settings.log_level.upper(),
        logging.INFO,
    ),
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("sara")


# ================================================================
# TOOL REGISTRATION
# ================================================================

def register_tools(bot: Bot) -> None:
    """
    SARA foydalanadigan barcha real Tool'larni
    Tool Registry'ga ulaydi.
    """

    # ============================================================
    # TELEGRAM TOOL
    # ============================================================

    configure_telegram_tool(bot)

    if not tool_registry.exists(
        "telegram_send_message"
    ):
        tool_registry.register(
            name="telegram_send_message",
            description=(
                "Telegram chat yoki guruhga "
                "xabar yuboradi."
            ),
            handler=send_telegram_message,
            enabled=True,
            dangerous=False,
            timeout=30,
        )

    # ============================================================
    # MEMORY TOOL
    # ============================================================

    if not tool_registry.exists(
        "memory"
    ):
        tool_registry.register(
            name="memory",
            description=(
                "SARA xotira tizimi. "
                "User va group memory saqlash, "
                "qidirish, ko'rish, o'chirish "
                "va sanash imkonini beradi."
            ),
            handler=memory_tool_handler,
            enabled=True,
            dangerous=False,
            timeout=30,
        )

    # ============================================================
    # REMINDER TOOL
    # ============================================================

    if not tool_registry.exists(
        "reminder"
    ):
        tool_registry.register(
            name="reminder",
            description=(
                "SARA reminder tizimi. "
                "Natural language orqali reminder yaratish, "
                "reminderlarni ko'rish, olish va bekor qilish "
                "imkonini beradi. Reminder DB'da saqlanadi "
                "va APScheduler orqali bajariladi."
            ),
            handler=reminder_tool_handler,
            enabled=True,
            dangerous=False,
            timeout=30,
        )

    # ============================================================
    # LOG
    # ============================================================

    logger.info(
        "Registered tools: %s",
        tool_registry.list_tools(
            enabled_only=True
        ),
    )


# ================================================================
# MAIN
# ================================================================

async def main() -> None:

    # ============================================================
    # CONFIG CHECK
    # ============================================================

    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN .env ichida sozlanmagan."
        )

    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY .env ichida sozlanmagan."
        )

    if not settings.openrouter_model:
        raise RuntimeError(
            "OPENROUTER_MODEL .env ichida sozlanmagan."
        )

    logger.info(
        "=========================================="
    )

    logger.info(
        "          SARA AI STARTING"
    )

    logger.info(
        "=========================================="
    )

    # ============================================================
    # DATABASE
    # ============================================================

    await init_database()

    logger.info(
        "Database tayyor."
    )

    # ============================================================
    # TELEGRAM
    # ============================================================

    bot = Bot(
        token=settings.bot_token
    )

    dispatcher = Dispatcher()

    dispatcher.include_router(
        create_router()
    )

    # ============================================================
    # TOOLS
    # ============================================================

    register_tools(
        bot
    )

    logger.info(
        "SARA Tool Registry: %s",
        tool_registry.stats(),
    )

    # ============================================================
    # SCHEDULER
    # ============================================================

    scheduler_manager.set_bot(
        bot
    )

    try:

        me = await bot.get_me()

        logger.info(
            "Telegram bot: @%s",
            me.username,
        )

        await bot.delete_webhook(
            drop_pending_updates=True
        )

        # ========================================================
        # REMINDERS
        # ========================================================

        if settings.reminder_enabled:

            scheduler_manager.start()

            logger.info(
                "Reminder Scheduler ishga tushdi."
            )

            restored = await restore_reminders()

            logger.info(
                "Restart recovery: %s ta reminder tiklandi.",
                restored,
            )

        else:

            logger.info(
                "Reminder system o'chirilgan."
            )

        # ========================================================
        # READY
        # ========================================================

        logger.info(
            "SARA AI ishga tushdi."
        )

        logger.info(
            "Memory Tool: ENABLED"
        )

        logger.info(
            "Telegram Tool: ENABLED"
        )

        logger.info(
            "Reminder Tool: ENABLED"
        )

        logger.info(
            "Agent Brain: ENABLED"
        )

        logger.info(
            "Agent Planner: ENABLED"
        )

        logger.info(
            "Agent Executor: ENABLED"
        )

        # ========================================================
        # POLLING
        # ========================================================

        await dispatcher.start_polling(
            bot
        )

    finally:

        logger.info(
            "SARA AI to'xtatilmoqda..."
        )

        # ========================================================
        # SCHEDULER STOP
        # ========================================================

        try:

            await scheduler_manager.stop()

        except Exception:

            logger.exception(
                "Scheduler stop xatosi."
            )

        # ========================================================
        # TELEGRAM CLOSE
        # ========================================================

        try:

            await bot.session.close()

        except Exception:

            logger.exception(
                "Telegram session close xatosi."
            )

        # ========================================================
        # DATABASE CLOSE
        # ========================================================

        try:

            await close_database()

        except Exception:

            logger.exception(
                "Database close xatosi."
            )

        logger.info(
            "SARA AI to'xtadi."
        )


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "SARA AI foydalanuvchi tomonidan to'xtatildi."
        )

    except Exception:

        logger.exception(
            "SARA AI critical error."
        )

        sys.exit(1)
