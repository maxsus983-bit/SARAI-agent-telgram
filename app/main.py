from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from app.agent.tools.memory_tool import memory_tool_handler
from app.agent.tools.registry import ToolDefinition, tool_registry
from app.agent.tools.reminder_tool import reminder_tool_handler
from app.agent.tools.telegram_tool import configure_telegram_tool

from app.bot.router import router

from app.config.settings import settings

from app.database.init import init_database, check_database
from app.database.session import close_database

from app.scheduler.manager import scheduler_manager
from app.scheduler.recovery import restore_reminders


# ================================================================
# LOGGING
# ================================================================

def configure_logging() -> None:
    """
    SARA logging tizimini ishga tushiradi.
    """

    level = getattr(
        logging,
        str(settings.log_level).upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
        stream=sys.stdout,
    )


logger = logging.getLogger("sara")


# ================================================================
# ENVIRONMENT VALIDATION
# ================================================================

def validate_settings() -> None:
    """
    Bot ishga tushishi uchun kerakli konfiguratsiyalarni tekshiradi.
    """

    missing: list[str] = []

    if not settings.bot_token.strip():
        missing.append("BOT_TOKEN")

    if not settings.openrouter_api_key.strip():
        missing.append("OPENROUTER_API_KEY")

    if not settings.openrouter_model.strip():
        missing.append("OPENROUTER_MODEL")

    if missing:
        raise RuntimeError(
            "Quyidagi environment variable'lar mavjud emas: "
            + ", ".join(missing)
        )


# ================================================================
# TOOL REGISTRY
# ================================================================

def register_tools() -> None:
    """
    SARA Agent Tool Registry'ga barcha asosiy tool'larni ulaydi.
    """

    # ------------------------------------------------------------
    # TELEGRAM
    # ------------------------------------------------------------

    async def telegram_handler(
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        **kwargs,
    ):
        """
        Telegram orqali xabar yuborish.
        """

        from app.agent.tools.telegram_tool import (
            send_telegram_message,
        )

        return await send_telegram_message(
            chat_id=int(chat_id),
            text=str(text),
            reply_to_message_id=(
                int(reply_to_message_id)
                if reply_to_message_id is not None
                else None
            ),
        )

    # ------------------------------------------------------------
    # TELEGRAM TOOL
    # ------------------------------------------------------------

    tool_registry.register(
        ToolDefinition(
            name="telegram_send_message",
            description=(
                "Telegram chat yoki guruhga SARA javobini "
                "yuboradi."
            ),
            handler=telegram_handler,
            enabled=True,
            dangerous=False,
            timeout=30.0,
            metadata={
                "category": "telegram",
                "autonomous": True,
            },
        )
    )

    # ------------------------------------------------------------
    # MEMORY TOOL
    # ------------------------------------------------------------

    async def memory_handler(
        *,
        operation: str,
        **kwargs,
    ):
        return await memory_tool_handler(
            operation=operation,
            **kwargs,
        )

    tool_registry.register(
        ToolDefinition(
            name="memory",
            description=(
                "SARA user va group memory tizimi. "
                "Saqlash, qidirish, olish, o'chirish, "
                "tiklash va sanash."
            ),
            handler=memory_handler,
            enabled=True,
            dangerous=False,
            timeout=30.0,
            metadata={
                "category": "memory",
                "persistent": True,
                "user_memory_in_group": True,
            },
        )
    )

    # ------------------------------------------------------------
    # REMINDER TOOL
    # ------------------------------------------------------------

    async def reminder_handler(
        *,
        operation: str,
        **kwargs,
    ):
        return await reminder_tool_handler(
            operation=operation,
            **kwargs,
        )

    tool_registry.register(
        ToolDefinition(
            name="reminder",
            description=(
                "Foydalanuvchi uchun reminder yaratish, "
                "olish, ro'yxatni ko'rish va bekor qilish."
            ),
            handler=reminder_handler,
            enabled=bool(settings.reminder_enabled),
            dangerous=False,
            timeout=30.0,
            metadata={
                "category": "scheduler",
                "persistent": True,
            },
        )
    )

    logger.info(
        "SARA tools registered: %s",
        ", ".join(
            tool.name
            for tool in tool_registry.list_tools()
        ),
    )


# ================================================================
# BOT STARTUP
# ================================================================

async def startup() -> tuple[Bot, Dispatcher]:
    """
    SARA'ni ishga tushiradi.
    """

    logger.info("=" * 70)
    logger.info("SARA AI starting...")
    logger.info("=" * 70)

    # ------------------------------------------------------------
    # CONFIG
    # ------------------------------------------------------------

    validate_settings()

    logger.info(
        "OpenRouter model: %s",
        settings.openrouter_model,
    )

    # ------------------------------------------------------------
    # DATABASE
    # ------------------------------------------------------------

    await init_database()

    database_ok = await check_database()

    if not database_ok:
        raise RuntimeError(
            "Database tekshiruvidan o'tmadi."
        )

    logger.info("Database ready.")

    # ------------------------------------------------------------
    # BOT
    # ------------------------------------------------------------

    bot = Bot(
        token=settings.bot_token,
    )

    dp = Dispatcher()

    # ------------------------------------------------------------
    # ROUTER
    # ------------------------------------------------------------

    dp.include_router(router)

    # ------------------------------------------------------------
    # TELEGRAM TOOL
    # ------------------------------------------------------------

    configure_telegram_tool(bot)

    # ------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------

    register_tools()

    # ------------------------------------------------------------
    # SCHEDULER
    # ------------------------------------------------------------

    scheduler_manager.set_bot(bot)

    scheduler_manager.start()

    logger.info("Scheduler started.")

    # ------------------------------------------------------------
    # REMINDER RECOVERY
    # ------------------------------------------------------------

    try:
        restored = await restore_reminders()

        logger.info(
            "Reminder recovery completed | restored=%s",
            restored,
        )

    except Exception:
        logger.exception(
            "Reminder recovery failed."
        )

    # ------------------------------------------------------------
    # BOT INFO
    # ------------------------------------------------------------

    me = await bot.get_me()

    logger.info(
        "Telegram bot connected | @%s | id=%s",
        me.username,
        me.id,
    )

    # ------------------------------------------------------------
    # WEBHOOK CLEANUP
    # ------------------------------------------------------------

    try:
        await bot.delete_webhook(
            drop_pending_updates=False,
        )

        logger.info(
            "Webhook removed. Polling mode ready."
        )

    except Exception:
        logger.exception(
            "Could not remove webhook."
        )

    # ------------------------------------------------------------
    # READY
    # ------------------------------------------------------------

    logger.info("=" * 70)
    logger.info("SARA AI IS READY")
    logger.info("=" * 70)

    logger.info(
        "Memory: %s",
        "ON" if settings.memory_enabled else "OFF",
    )

    logger.info(
        "Proactive groups: %s",
        "ON" if settings.proactive_group_mode else "OFF",
    )

    logger.info(
        "Reminders: %s",
        "ON" if settings.reminder_enabled else "OFF",
    )

    logger.info(
        "Bot-to-bot: %s",
        "ON" if settings.bot_to_bot_mode else "OFF",
    )

    logger.info(
        "Media: %s",
        "ON" if settings.media_enabled else "OFF",
    )

    return bot, dp


# ================================================================
# POLLING
# ================================================================

async def run() -> None:
    """
    SARA Telegram polling loop.
    """

    bot: Bot | None = None

    try:

        bot, dp = await startup()

        logger.info(
            "SARA polling started."
        )

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    except asyncio.CancelledError:

        logger.info(
            "SARA polling cancelled."
        )

        raise

    except KeyboardInterrupt:

        logger.info(
            "SARA stopped by keyboard."
        )

    except Exception:

        logger.exception(
            "Fatal SARA runtime error."
        )

        raise

    finally:

        # --------------------------------------------------------
        # SCHEDULER
        # --------------------------------------------------------

        try:
            scheduler_manager.stop()

            logger.info(
                "Scheduler stopped."
            )

        except Exception:
            logger.exception(
                "Scheduler shutdown failed."
            )

        # --------------------------------------------------------
        # BOT
        # --------------------------------------------------------

        if bot is not None:

            try:
                await bot.session.close()

                logger.info(
                    "Telegram bot session closed."
                )

            except Exception:
                logger.exception(
                    "Bot session close failed."
                )

        # --------------------------------------------------------
        # DATABASE
        # --------------------------------------------------------

        try:
            await close_database()

            logger.info(
                "Database connection closed."
            )

        except Exception:
            logger.exception(
                "Database shutdown failed."
            )

        logger.info(
            "SARA AI shutdown completed."
        )


# ================================================================
# MAIN
# ================================================================

def main() -> None:
    """
    Application entry point.
    """

    configure_logging()

    try:
        asyncio.run(run())

    except KeyboardInterrupt:
        logger.info(
            "SARA terminated."
        )

    except Exception:
        logger.exception(
            "SARA terminated because of an error."
        )

        raise


if __name__ == "__main__":
    main()
