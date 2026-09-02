from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# SARA AI
# Main Application
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def setup_logging() -> None:
    """
    Configure SARA logging.
    """

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()

    level = getattr(
        logging,
        level_name,
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
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Reduce noisy third-party logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING
    )


logger = logging.getLogger("sara")


def validate_environment() -> None:
    """
    Validate mandatory environment variables.
    """

    required = [
        "BOT_TOKEN",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
    ]

    missing = []

    for variable in required:
        value = os.getenv(variable, "").strip()

        if not value:
            missing.append(variable)

    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


def print_startup_banner() -> None:
    """
    Display SARA startup information.
    """

    memory = os.getenv(
        "MEMORY_ENABLED",
        "true",
    )

    proactive = os.getenv(
        "PROACTIVE_GROUP_MODE",
        "true",
    )

    reminders = os.getenv(
        "REMINDER_ENABLED",
        "true",
    )

    bot_to_bot = os.getenv(
        "BOT_TO_BOT_MODE",
        "true",
    )

    print()
    print("=" * 60)
    print("                    SARA AI")
    print("              TELEGRAM AI AGENT")
    print("=" * 60)
    print(
        f"Memory          : "
        f"{'ON' if memory.lower() == 'true' else 'OFF'}"
    )
    print(
        f"Proactive Mode  : "
        f"{'ON' if proactive.lower() == 'true' else 'OFF'}"
    )
    print(
        f"Reminders       : "
        f"{'ON' if reminders.lower() == 'true' else 'OFF'}"
    )
    print(
        f"Bot-to-Bot      : "
        f"{'ON' if bot_to_bot.lower() == 'true' else 'OFF'}"
    )
    print("=" * 60)
    print()


async def main() -> None:
    """
    SARA application entry point.

    More services will be connected here:
        - Database
        - Telegram Bot
        - OpenRouter
        - Memory Engine
        - Scheduler
        - Agent Engine
    """

    setup_logging()

    logger.info("Starting SARA AI...")

    validate_environment()

    print_startup_banner()

    logger.info("Environment: READY")
    logger.info("SARA core: READY")

    # Temporary event loop until the real Telegram
    # application is connected.
    stop_event = asyncio.Event()

    try:
        await stop_event.wait()

    except asyncio.CancelledError:
        logger.info("Shutdown signal received.")

        raise

    finally:
        logger.info("SARA AI stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("SARA stopped by user.")

    except Exception:
        logger.exception("Fatal SARA error.")
        sys.exit(1)
