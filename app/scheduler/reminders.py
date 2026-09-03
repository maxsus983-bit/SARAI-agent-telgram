from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Any

from app.config.settings import settings


# ============================================================
# PARSED REMINDER
# ============================================================

@dataclass(slots=True)
class ParsedReminder:
    text: str
    remind_at: datetime


# ============================================================
# TIMEZONE
# ============================================================

def _timezone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def _now() -> datetime:
    return datetime.now(_timezone())


# ============================================================
# FORMAT
# ============================================================

def format_reminder_time(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone())

    dt = dt.astimezone(_timezone())

    return dt.strftime("%d.%m.%Y %H:%M")


# ============================================================
# TEXT CLEANING
# ============================================================

def _clean_reminder_text(text: str) -> str:
    text = str(text or "").strip()

    if not text:
        return ""

    text = re.sub(
        r"\s+",
        " ",
        text,
        flags=re.UNICODE,
    )

    # Common Uzbek reminder endings
    patterns = [
        r"\s+(?:menga\s+)?eslat(?:ib)?\s*(?:qo['’`]?y)?[.!]?$",
        r"\s+(?:menga\s+)?eslat[.!]?$",
        r"\s+eslatib\s+qo['’`]?y[.!]?$",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    return text.strip(" .,!?")



# ============================================================
# CLOCK HELPERS
# ============================================================

def _next_clock_time(
    hour: int,
    minute: int,
) -> datetime:

    now = _now()

    target = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if target <= now:
        target += timedelta(days=1)

    return target


# ============================================================
# PARSER
# ============================================================

def parse_reminder(text: str) -> ParsedReminder | None:
    """
    Uzbek/English oddiy reminder parser.

    Qo‘llab-quvvatlanadi:

        10 daqiqadan keyin menga eslat
        30 minutdan keyin eslat
        2 soatdan keyin eslat
        1 kundan keyin eslat
        2 haftadan keyin eslat

        bugun 20:00 da eslat
        ertaga 09:30 da eslat
        soat 18:00 da eslat

        remind me in 10 minutes
        remind me in 2 hours
        remind me tomorrow at 09:00
    """

    original = str(text or "").strip()

    if not original:
        return None

    lowered = original.lower()

    now = _now()

    # ========================================================
    # RELATIVE TIME
    # ========================================================

    relative_patterns = [
        (
            r"(\d+)\s*(?:daqiqa|minut|minute|minutes?|mins?)"
            r"\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "minutes",
        ),
        (
            r"(\d+)\s*(?:soat|hour|hours?)"
            r"\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "hours",
        ),
        (
            r"(\d+)\s*(?:kun|days?)"
            r"\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "days",
        ),
        (
            r"(\d+)\s*(?:hafta|weeks?)"
            r"\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "weeks",
        ),
    ]

    for pattern, unit in relative_patterns:

        match = re.search(
            pattern,
            lowered,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        amount = int(match.group(1))

        if amount <= 0:
            return None

        if unit == "minutes":
            remind_at = now + timedelta(
                minutes=amount
            )

        elif unit == "hours":
            remind_at = now + timedelta(
                hours=amount
            )

        elif unit == "days":
            remind_at = now + timedelta(
                days=amount
            )

        else:
            remind_at = now + timedelta(
                weeks=amount
            )

        reminder_text = _clean_reminder_text(
            original
        )

        if not reminder_text:
            reminder_text = "Reminder"

        return ParsedReminder(
            text=reminder_text,
            remind_at=remind_at,
        )

    # ========================================================
    # ENGLISH "IN N MINUTES"
    # ========================================================

    english_relative = re.search(
        r"\bin\s+(\d+)\s+"
        r"(minute|minutes|min|hour|hours|day|days|week|weeks)\b",
        lowered,
        flags=re.IGNORECASE,
    )

    if english_relative:

        amount = int(
            english_relative.group(1)
        )

        unit = (
            english_relative
            .group(2)
            .lower()
        )

        if amount <= 0:
            return None

        if unit.startswith("min"):
            remind_at = now + timedelta(
                minutes=amount
            )
        elif unit.startswith("hour"):
            remind_at = now + timedelta(
                hours=amount
            )
        elif unit.startswith("day"):
            remind_at = now + timedelta(
                days=amount
            )
        else:
            remind_at = now + timedelta(
                weeks=amount
            )

        reminder_text = _clean_reminder_text(
            original
        )

        reminder_text = re.sub(
            r"\bremind\s+me\b",
            "",
            reminder_text,
            flags=re.IGNORECASE,
        )

        reminder_text = re.sub(
            r"\bin\s+\d+\s+"
            r"(?:minute|minutes|min|hour|hours|day|days|week|weeks)\b",
            "",
            reminder_text,
            flags=re.IGNORECASE,
        )

        reminder_text = re.sub(
            r"\s+",
            " ",
            reminder_text,
        ).strip(" .,!?")

        if not reminder_text:
            reminder_text = "Reminder"

        return ParsedReminder(
            text=reminder_text,
            remind_at=remind_at,
        )

    # ========================================================
    # CLOCK TIME
    # ========================================================

    clock_pattern = re.compile(
        r"(?:soat\s*)?"
        r"(\d{1,2})[:.](\d{2})"
        r"(?:\s*(?:da|ga))?",
        flags=re.IGNORECASE,
    )

    clock_match = clock_pattern.search(
        lowered
    )

    if clock_match:

        hour = int(
            clock_match.group(1)
        )

        minute = int(
            clock_match.group(2)
        )

        if not (
            0 <= hour <= 23
            and 0 <= minute <= 59
        ):
            return None

        # ----------------------------------------------------
        # ERTAGA
        # ----------------------------------------------------

        if "ertaga" in lowered:

            tomorrow = now + timedelta(
                days=1
            )

            remind_at = tomorrow.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        # ----------------------------------------------------
        # BUGUN
        # ----------------------------------------------------

        elif "bugun" in lowered:

            remind_at = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            if remind_at <= now:
                return None

        # ----------------------------------------------------
        # JUST CLOCK
        # ----------------------------------------------------

        else:

            remind_at = _next_clock_time(
                hour,
                minute,
            )

        reminder_text = _clean_reminder_text(
            original
        )

        reminder_text = re.sub(
            r"\b(?:bugun|ertaga)\b",
            "",
            reminder_text,
            flags=re.IGNORECASE,
        )

        reminder_text = re.sub(
            r"\b(?:soat\s*)?"
            r"\d{1,2}[:.]\d{2}"
            r"\s*(?:da|ga)?\b",
            "",
            reminder_text,
            flags=re.IGNORECASE,
        )

        reminder_text = re.sub(
            r"\s+",
            " ",
            reminder_text,
        ).strip(" .,!?")

        if not reminder_text:
            reminder_text = "Reminder"

        return ParsedReminder(
            text=reminder_text,
            remind_at=remind_at,
        )

    # ========================================================
    # FALLBACK: "N DAQIQA"
    # ========================================================

    simple_match = re.search(
        r"(\d+)\s*"
        r"(?:m|min|m\.|daq|daqiqa|minut|minute)"
        r"\b",
        lowered,
    )

    if simple_match and (
        "keyin" in lowered
        or "so'ng" in lowered
        or "so‘ng" in lowered
    ):

        amount = int(
            simple_match.group(1)
        )

        if amount <= 0:
            return None

        remind_at = now + timedelta(
            minutes=amount
        )

        reminder_text = _clean_reminder_text(
            original
        )

        if not reminder_text:
            reminder_text = "Reminder"

        return ParsedReminder(
            text=reminder_text,
            remind_at=remind_at,
        )

    return None


# ============================================================
# SCHEDULER MANAGER IMPORT
# ============================================================

def _get_scheduler_manager():
    """
    Lazy import.

    Bu juda muhim:
    scheduler.reminders
        ↓
    scheduler.manager
        ↓
    reminders

    kabi circular import bo‘lib qolmasligi uchun
    import faqat funksiya chaqirilganda qilinadi.
    """

    from app.scheduler.manager import scheduler_manager

    return scheduler_manager


# ============================================================
# CREATE REMINDER
# ============================================================

async def create_reminder(
    *,
    owner_telegram_id: int,
    chat_id: int,
    text: str,
    remind_at: datetime,
):
    """
    Reminder yaratadi.
    """

    if not text or not str(text).strip():
        raise ValueError(
            "Reminder text bo‘sh bo‘lishi mumkin emas."
        )

    if remind_at.tzinfo is None:
        remind_at = remind_at.replace(
            tzinfo=_timezone()
        )

    if remind_at <= _now():
        raise ValueError(
            "Reminder vaqti kelajakda bo‘lishi kerak."
        )

    scheduler_manager = (
        _get_scheduler_manager()
    )

    return await scheduler_manager.create_reminder(
        owner_telegram_id=int(
            owner_telegram_id
        ),
        chat_id=int(chat_id),
        text=str(text).strip(),
        remind_at=remind_at,
    )


# ============================================================
# CREATE REMINDER FROM TEXT
# ============================================================

async def create_reminder_from_text(
    *,
    owner_telegram_id: int | None = None,
    chat_id: int | None = None,
    user_id: int | None = None,
    text: str | None = None,
    reminder_text: str | None = None,
    message: str | None = None,
    **kwargs: Any,
):
    """
    commands.py uchun asosiy compatibility API.

    Masalan:

        create_reminder_from_text(
            owner_telegram_id=123,
            chat_id=456,
            text="10 daqiqadan keyin menga eslat"
        )

    yoki:

        create_reminder_from_text(
            user_id=123,
            chat_id=456,
            text="ertaga 09:00 da menga uchrashuvni eslat"
        )
    """

    # owner ID
    if owner_telegram_id is None:
        owner_telegram_id = user_id

    if owner_telegram_id is None:
        raise ValueError(
            "owner_telegram_id kerak."
        )

    # chat ID
    if chat_id is None:
        chat_id = kwargs.get(
            "telegram_chat_id"
        )

    if chat_id is None:
        raise ValueError(
            "chat_id kerak."
        )

    # Text
    source_text = (
        text
        or reminder_text
        or message
        or ""
    )

    source_text = str(
        source_text
    ).strip()

    if not source_text:
        raise ValueError(
            "Reminder text bo‘sh."
        )

    # Parse
    parsed = parse_reminder(
        source_text
    )

    if parsed is None:
        raise ValueError(
            "Reminder vaqtini tushunib bo‘lmadi. "
            "Masalan: '10 daqiqadan keyin menga eslat' "
            "yoki 'ertaga 09:00 da eslat'."
        )

    return await create_reminder(
        owner_telegram_id=int(
            owner_telegram_id
        ),
        chat_id=int(chat_id),
        text=parsed.text,
        remind_at=parsed.remind_at,
    )


# ============================================================
# GET REMINDER
# ============================================================

async def get_reminder_by_id(
    reminder_id: int,
    owner_telegram_id: int | None = None,
    user_id: int | None = None,
):
    """
    Bitta reminder olish.
    """

    if owner_telegram_id is None:
        owner_telegram_id = user_id

    if owner_telegram_id is None:
        raise ValueError(
            "owner_telegram_id kerak."
        )

    scheduler_manager = (
        _get_scheduler_manager()
    )

    return await scheduler_manager.get_reminder(
        reminder_id=int(reminder_id),
        owner_telegram_id=int(
            owner_telegram_id
        ),
    )


# ============================================================
# CANCEL REMINDER
# ============================================================

async def cancel_reminder_by_id(
    reminder_id: int,
    owner_telegram_id: int | None = None,
    user_id: int | None = None,
) -> bool:
    """
    Reminderni bekor qiladi.

    Faqat reminder egasi bekor qila oladi.
    """

    if owner_telegram_id is None:
        owner_telegram_id = user_id

    if owner_telegram_id is None:
        raise ValueError(
            "owner_telegram_id kerak."
        )

    scheduler_manager = (
        _get_scheduler_manager()
    )

    return await scheduler_manager.cancel_reminder(
        reminder_id=int(reminder_id),
        owner_telegram_id=int(
            owner_telegram_id
        ),
    )


# ============================================================
# GET USER REMINDERS
# ============================================================

async def get_user_reminders(
    owner_telegram_id: int | None = None,
    *,
    user_id: int | None = None,
    include_completed: bool = False,
):
    """
    Foydalanuvchining reminderlari.
    """

    if owner_telegram_id is None:
        owner_telegram_id = user_id

    if owner_telegram_id is None:
        raise ValueError(
            "owner_telegram_id kerak."
        )

    scheduler_manager = (
        _get_scheduler_manager()
    )

    return await scheduler_manager.get_user_reminders(
        int(owner_telegram_id),
        include_completed=include_completed,
    )


# ============================================================
# ACTIVE REMINDERS
# ============================================================

async def get_active_reminders():
    """
    Barcha aktiv reminderlar.
    """

    scheduler_manager = (
        _get_scheduler_manager()
    )

    return await scheduler_manager.get_active_reminders()


# ============================================================
# ALIASES
# ============================================================

# Eski kodlarda boshqa nom ishlatilgan bo‘lsa,
# compatibility uchun aliaslar.

parse_reminder_text = parse_reminder

create_from_text = create_reminder_from_text

cancel_reminder = cancel_reminder_by_id

get_reminder = get_reminder_by_id


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "ParsedReminder",

    "parse_reminder",
    "parse_reminder_text",

    "format_reminder_time",

    "create_reminder",
    "create_reminder_from_text",
    "create_from_text",

    "get_reminder_by_id",
    "get_reminder",

    "cancel_reminder_by_id",
    "cancel_reminder",

    "get_user_reminders",
    "get_active_reminders",
            ]
