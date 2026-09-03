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
    SARA AI logging tizimini ishga tushiradi.
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
        force=True,
    )


logger = logging.getLogger("sara")


# ================================================================
# ENVIRONMENT VALIDATION
# ================================================================

def validate_settings() -> None:
    """
    SARA AI ishga tushishi uchun kerakli environment
    variable'larni tekshiradi.
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

_tools_registered = False


def register_tools() -> None:
    """
    SARA Agent Tool Registry'ga barcha asosiy tool'larni ulaydi.

    ToolRegistry hozirgi versiyada quyidagi ikkala uslubni
    qo'llashi mumkin:

        register(ToolDefinition(...))

    yoki:

        register(name, description, handler)

    Biz bu yerda ToolDefinition uslubidan foydalanamiz.
    """

    global _tools_registered

    if _tools_registered:
        logger.debug(
            "SARA tools allaqachon registered. Qayta ro'yxatdan o'tkazilmaydi."
        )
        return

    # ============================================================
    # TELEGRAM TOOL HANDLER
    # ============================================================

    async def telegram_handler(
        *,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        **kwargs,
    ):
        """
        Telegram chat yoki guruhga xabar yuborish.
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

    # ============================================================
    # MEMORY TOOL HANDLER
    # ============================================================

    async def memory_handler(
        *,
        operation: str,
        **kwargs,
    ):
        """
        SARA memory tool wrapper.
        """

        return await memory_tool_handler(
            operation=operation,
            **kwargs,
        )

    # ============================================================
    # REMINDER TOOL HANDLER
    # ============================================================

    async def reminder_handler(
        *,
        operation: str,
        **kwargs,
    ):
        """
        SARA reminder tool wrapper.
        """

        return await reminder_tool_handler(
            operation=operation,
            **kwargs,
        )

    # ============================================================
    # TELEGRAM
    # ============================================================

    tool_registry.register(
        ToolDefinition(
            name="telegram_send_message",
            description=(
                "Telegram chat yoki guruhga SARA xabarini "
                "yuboradi. Reply qilish imkoniyatini ham qo'llaydi."
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

    # ============================================================
    # MEMORY
    # ============================================================

    tool_registry.register(
        ToolDefinition(
            name="memory",
            description=(
                "SARA AI persistent memory tizimi. "
                "User memory, group memory va conversation "
                "memory bilan ishlaydi. Saqlash, qidirish, "
                "olish, o'chirish, tiklash va sanash "
                "operatsiyalarini bajaradi."
            ),
            handler=memory_handler,
            enabled=bool(settings.memory_enabled),
            dangerous=False,
            timeout=30.0,
            metadata={
                "category": "memory",
                "persistent": True,
                "user_memory_in_group": True,
            },
        )
    )

    # ============================================================
    # REMINDER
    # ============================================================

    tool_registry.register(
        ToolDefinition(
            name="reminder",
            description=(
                "Foydalanuvchi uchun reminder yaratadi, "
                "mavjud reminderlarni ko'rsatadi, "
                "bitta reminder haqida ma'lumot beradi "
                "va reminderlarni bekor qiladi."
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

    _tools_registered = True

    # ============================================================
    # LOG
    # ============================================================

    try:
        tools = tool_registry.list_tools()

        logger.info(
            "SARA tools registered: %s",
            ", ".join(tool.name for tool in tools),
        )

    except Exception:
        logger.exception(
            "Tool registry ro'yxatini chiqarishda xatolik."
        )


# ================================================================
# BOT STARTUP
# ================================================================

async def startup() -> tuple[Bot, Dispatcher]:
    """
    SARA AI application startup.

    Tartib:

        1. Settings
        2. Database
        3. Telegram Bot
        4. Router
        5. Telegram Tool
        6. Agent Tools
        7. Scheduler
        8. Reminder recovery
        9. Telegram connection
        10. Polling ready
    """

    logger.info("=" * 70)
    logger.info("SARA AI starting...")
    logger.info("=" * 70)

    # ============================================================
    # CONFIGURATION
    # ============================================================

    validate_settings()

    logger.info(
        "OpenRouter model: %s",
        settings.openrouter_model,
    )

    # ============================================================
    # DATABASE
    # ============================================================

    await init_database()

    database_ok = await check_database()

    if not database_ok:
        raise RuntimeError(
            "Database tekshiruvidan o'tmadi."
        )

    logger.info("Database ready.")

    # ============================================================
    # TELEGRAM BOT
    # ============================================================

    bot = Bot(
        token=settings.bot_token,
    )

    dp = Dispatcher()

    # ============================================================
    # ROUTER
    # ============================================================

    dp.include_router(router)

    logger.info(
        "Telegram router loaded."
    )

    # ============================================================
    # TELEGRAM TOOL
    # ============================================================

    configure_telegram_tool(bot)

    logger.info(
        "Telegram Tool configured."
    )

    # ============================================================
    # AGENT TOOLS
    # ============================================================

    register_tools()

    # ============================================================
    # SCHEDULER
    # ============================================================

    scheduler_manager.set_bot(bot)

    scheduler_manager.start()

    logger.info(
        "Scheduler started."
    )

    # ============================================================
    # REMINDER RECOVERY
    # ============================================================

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

    # ============================================================
    # TELEGRAM CONNECTION CHECK
    # ============================================================

    me = await bot.get_me()

    logger.info(
        "Telegram bot connected | @%s | id=%s",
        me.username,
        me.id,
    )

    # ============================================================
    # WEBHOOK CLEANUP
    # ============================================================

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

    # ============================================================
    # READY INFORMATION
    # ============================================================

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

    logger.info(
        "Timezone: %s",
        settings.timezone,
    )

    return bot, dp


# ================================================================
# CLEANUP
# ================================================================

async def shutdown(bot: Bot | None = None) -> None:
    """
    SARA AI barcha resurslarini xavfsiz yopadi.

    Muhim:
        scheduler_manager.stop() async bo'lgani uchun
        bu yerda ALBATTA await ishlatiladi.
    """

    logger.info(
        "SARA AI shutdown started..."
    )

    # ============================================================
    # SCHEDULER
    # ============================================================

    try:

        await scheduler_manager.stop()

        logger.info(
            "Scheduler stopped."
        )

    except Exception:

        logger.exception(
            "Scheduler shutdown failed."
        )

    # ============================================================
    # TELEGRAM BOT
    # ============================================================

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

    # ============================================================
    # DATABASE
    # ============================================================

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
# POLLING
# ================================================================

async def run() -> None:
    """
    SARA Telegram polling loop.
    """

    bot: Bot | None = None

    try:

        # --------------------------------------------------------
        # STARTUP
        # --------------------------------------------------------

        bot, dp = await startup()

        logger.info(
            "SARA polling started."
        )

        # --------------------------------------------------------
        # POLLING
        # --------------------------------------------------------

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

        await shutdown(bot)


# ================================================================
# MAIN
# ================================================================

def main() -> None:
    """
    SARA AI application entry point.
    """

    configure_logging()

    logger.info(
        "SARA AI process starting..."
    )

    try:

        asyncio.run(run())

    except KeyboardInterrupt:

        logger.info(
            "SARA terminated by keyboard."
        )

    except Exception:

        logger.exception(
            "SARA terminated because of an error."
        )

        raise


# ================================================================
# PYTHON ENTRY POINT
# ================================================================

if __name__ == "__main__":
    main()
