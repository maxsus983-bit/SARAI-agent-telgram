from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from app.agent.tools.memory_tool import memory_tool_handler
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


def register_tools(bot: Bot) -> None:
    """
    SARA foydalanadigan barcha real tool'larni
    Tool Registry'ga ulaydi.
    """

    # =========================================================
    # TELEGRAM TOOL
    # =========================================================

    configure_telegram_tool(bot)

    if not tool_registry.exists("telegram_send_message"):
        tool_registry.register(
            name="telegram_send_message",
            description=(
                "Telegram chat yoki guruhga xabar yuboradi. "
                "SARA mustaqil ravishda javob yoki xabar yuborishi mumkin."
            ),
            handler=send_telegram_message,
            enabled=True,
            dangerous=False,
            timeout=30,
        )

    # =========================================================
    # MEMORY TOOL
    # =========================================================

    if not tool_registry.exists("memory"):
        tool_registry.register(
            name="memory",
            description=(
                "SARA xotira tizimi. "
                "User va group memory saqlash, qidirish, "
                "ko'rish, o'chirish va sanash imkonini beradi. "
                "SARA suhbatlardan kerakli ma'lumotlarni "
                "uzoq muddatli xotiraga saqlashi mumkin."
            ),
            handler=memory_tool_handler,
            enabled=True,
            dangerous=False,
            timeout=30,
        )

    logger.info(
        "Registered tools: %s",
        tool_registry.list_tools(enabled_only=True),
    )


async def main() -> None:
    # =========================================================
    # CONFIG CHECK
    # =========================================================

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

    logger.info("==========================================")
    logger.info("          SARA AI STARTING")
    logger.info("==========================================")

    # =========================================================
    # DATABASE
    # =========================================================

    await init_database()

    logger.info("Database tayyor.")

    # =========================================================
    # TELEGRAM
    # =========================================================

    bot = Bot(token=settings.bot_token)

    dispatcher = Dispatcher()

    dispatcher.include_router(
        create_router()
    )

    # =========================================================
    # AGENT TOOLS
    # =========================================================

    register_tools(bot)

    logger.info(
        "SARA Tool Registry: %s",
        tool_registry.stats(),
    )

    # =========================================================
    # SCHEDULER
    # =========================================================

    scheduler_manager.set_bot(bot)

    try:
        me = await bot.get_me()

        logger.info(
            "Telegram bot: @%s",
            me.username,
        )

        await bot.delete_webhook(
            drop_pending_updates=True
        )

        # =====================================================
        # REMINDERS
        # =====================================================

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

        # =====================================================
        # READY
        # =====================================================

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
            "Agent Brain: ENABLED"
        )

        logger.info(
            "Agent Planner: ENABLED"
        )

        logger.info(
            "Agent Executor: ENABLED"
        )

        await dispatcher.start_polling(
            bot
        )

    finally:
        logger.info(
            "SARA AI to'xtatilmoqda..."
        )

        try:
            await scheduler_manager.stop()

        except Exception:
            logger.exception(
                "Scheduler stop xatosi."
            )

        try:
            await bot.session.close()

        except Exception:
            logger.exception(
                "Telegram session close xatosi."
            )

        try:
            await close_database()

        except Exception:
            logger.exception(
                "Database close xatosi."
            )

        logger.info(
            "SARA AI to'xtadi."
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info(
            "SARA AI foydalanuvchi tomonidan to'xtatildi."
        )

    except Exception:
        logger.exception(
            "SARA AI critical error."
        )

        sys.exit(1)
