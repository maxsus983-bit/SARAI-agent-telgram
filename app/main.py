from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

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

    logger.info(
        "Database ishga tushirilmoqda..."
    )

    await init_database()

    logger.info(
        "Database tayyor."
    )

    # ============================================================
    # BOT
    # ============================================================

    bot = Bot(
        token=settings.bot_token
    )

    dispatcher = Dispatcher()

    dispatcher.include_router(
        create_router()
    )

    # ============================================================
    # SCHEDULER BOT BILAN BOG'LANADI
    # ============================================================

    scheduler_manager.set_bot(
        bot
    )

    # ============================================================
    # START
    # ============================================================

    try:

        me = await bot.get_me()

        logger.info(
            "Telegram bot: @%s",
            me.username,
        )

        # --------------------------------------------------------
        # Webhookni tozalash
        # --------------------------------------------------------

        await bot.delete_webhook(
            drop_pending_updates=True
        )

        # --------------------------------------------------------
        # Scheduler start
        # --------------------------------------------------------

        if settings.reminder_enabled:

            scheduler_manager.start()

            logger.info(
                "Reminder Scheduler ishga tushdi."
            )

            # ----------------------------------------------------
            # Restartdan keyingi recovery
            # ----------------------------------------------------

            restored = await restore_reminders()

            logger.info(
                "Restart recovery: %s ta reminder tiklandi.",
                restored,
            )

        else:

            logger.info(
                "Reminder system .env orqali o'chirilgan."
            )

        # --------------------------------------------------------
        # POLLING
        # --------------------------------------------------------

        logger.info(
            "SARA AI ishga tushdi."
        )

        await dispatcher.start_polling(
            bot
        )

    finally:

        logger.info(
            "SARA AI to'xtatilmoqda..."
        )

        # --------------------------------------------------------
        # Scheduler stop
        # --------------------------------------------------------

        try:
            await scheduler_manager.stop()
        except Exception:
            logger.exception(
                "Scheduler stop xatosi."
            )

        # --------------------------------------------------------
        # Bot close
        # --------------------------------------------------------

        try:
            await bot.session.close()
        except Exception:
            logger.exception(
                "Telegram session close xatosi."
            )

        # --------------------------------------------------------
        # Database close
        # --------------------------------------------------------

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
