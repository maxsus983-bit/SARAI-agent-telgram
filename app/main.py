from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from app.bot.router import create_router
from app.config.settings import settings
from app.database.init import init_database
from app.database.session import close_database


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
        "        SARA AI STARTING"
    )

    logger.info(
        "=========================================="
    )

    # ----------------------------------------------------------
    # DATABASE
    # ----------------------------------------------------------

    logger.info(
        "Database ishga tushirilmoqda..."
    )

    await init_database()

    logger.info(
        "Database tayyor."
    )

    # ----------------------------------------------------------
    # BOT
    # ----------------------------------------------------------

    bot = Bot(
        token=settings.bot_token
    )

    dispatcher = Dispatcher()

    dispatcher.include_router(
        create_router()
    )

    try:

        me = await bot.get_me()

        logger.info(
            "Telegram bot: @%s",
            me.username,
        )

        logger.info(
            "SARA AI ishga tushdi."
        )

        # Eski pending update'larni tashlab yuborish.
        await bot.delete_webhook(
            drop_pending_updates=True
        )

        await dispatcher.start_polling(
            bot
        )

    finally:

        logger.info(
            "SARA AI to'xtatilmoqda..."
        )

        await bot.session.close()

        await close_database()


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:

        logger.info(
            "SARA AI to'xtatildi."
        )

    except Exception:

        logger.exception(
            "SARA AI critical error."
        )

        sys.exit(1)
