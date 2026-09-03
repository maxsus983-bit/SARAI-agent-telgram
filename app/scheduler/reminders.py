from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config.settings import settings


@dataclass(slots=True)
class ParsedReminder:
    text: str
    remind_at: datetime


def _timezone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def format_reminder_time(dt: datetime) -> str:
    """Reminder vaqtini foydalanuvchiga chiroyli ko‘rsatish."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone())

    dt = dt.astimezone(_timezone())
    return dt.strftime("%d.%m.%Y %H:%M")


def _clean_reminder_text(text: str) -> str:
    """Reminder matnini tozalash."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()

    patterns = [
        r"\s+(?:menga\s+)?eslat(?:ib)?\s*(?:qo['’`]?y)?[.!]?$",
        r"\s+(?:menga\s+)?eslat[.!]?$",
    ]

    for pattern in patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.IGNORECASE,
        )

    return text.strip(" .,!?")



def _today_at(hour: int, minute: int) -> datetime:
    now = datetime.now(_timezone())

    return now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def _next_clock_time(hour: int, minute: int) -> datetime:
    now = datetime.now(_timezone())

    target = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if target <= now:
        target += timedelta(days=1)

    return target


def parse_reminder(text: str) -> ParsedReminder | None:
    """
    Oddiy Uzbek reminder gaplarini parse qiladi.

    Misollar:

        10 daqiqadan keyin menga eslat
        2 soatdan keyin menga eslat
        1 kundan keyin eslat
        bugun 20:00 da eslat
        ertaga 09:30 da eslat
        soat 18:00 da eslat

    Natija:
        ParsedReminder | None
    """

    original = str(text or "").strip()

    if not original:
        return None

    lowered = original.lower().strip()

    now = datetime.now(_timezone())

    # ---------------------------------------------------------
    # 1. N DAQIQA / SOAT / KUN / HAFTADAN KEYIN
    # ---------------------------------------------------------

    relative_patterns = [
        (
            r"(\d+)\s*(?:daqiqa|minut|minute)\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "minutes",
        ),
        (
            r"(\d+)\s*(?:soat|hour|hours)\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "hours",
        ),
        (
            r"(\d+)\s*(?:kun|days?)\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
            "days",
        ),
        (
            r"(\d+)\s*(?:hafta|weeks?)\s*(?:dan\s*)?(?:keyin|so['’`]?ng)",
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
            remind_at = now + timedelta(minutes=amount)

        elif unit == "hours":
            remind_at = now + timedelta(hours=amount)

        elif unit == "days":
            remind_at = now + timedelta(days=amount)

        else:
            remind_at = now + timedelta(weeks=amount)

        reminder_text = _clean_reminder_text(original)

        if not reminder_text:
            reminder_text = "Reminder"

        return ParsedReminder(
            text=reminder_text,
            remind_at=remind_at,
        )

    # ---------------------------------------------------------
    # 2. BUGUN / ERTAGA + SOAT
    # ---------------------------------------------------------

    clock_pattern = re.compile(
        r"(?:soat\s*)?(\d{1,2})[:.](\d{2})"
        r"(?:\s*(?:da|ga))?",
        flags=re.IGNORECASE,
    )

    clock_match = clock_pattern.search(lowered)

    if clock_match:
        hour = int(clock_match.group(1))
        minute = int(clock_match.group(2))

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None

        if "ertaga" in lowered:
            base = now + timedelta(days=1)

            remind_at = base.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

        elif "bugun" in lowered:
            remind_at = now.replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )

            # Bugungi vaqt allaqachon o'tgan bo‘lsa,
            # keyingi kunga o'tkazmaymiz.
            # Chunki "bugun 08:00" noto‘g‘ri vaqt bo‘lishi mumkin.
            if remind_at <= now:
                return None

        else:
            remind_at = _next_clock_time(
                hour,
                minute,
            )

        reminder_text = _clean_reminder_text(original)

        # "bugun", "ertaga", "soat..." qismlarini matndan olib tashlash
        reminder_text = re.sub(
            r"\b(?:bugun|ertaga)\b",
            "",
            reminder_text,
            flags=re.IGNORECASE,
        )

        reminder_text = re.sub(
            r"\b(?:soat\s*)?\d{1,2}[:.]\d{2}\s*(?:da|ga)?\b",
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

    # ---------------------------------------------------------
    # 3. ODDIY "N DAQIQADAN KEYIN"
    # ---------------------------------------------------------

    simple_match = re.search(
        r"(\d+)\s*(?:m|min|m\.|daq|daqiqa)\b",
        lowered,
    )

    if simple_match and (
        "keyin" in lowered
        or "so'ng" in lowered
        or "so‘ng" in lowered
    ):
        amount = int(simple_match.group(1))

        if amount <= 0:
            return None

        remind_at = now + timedelta(
            minutes=amount
        )

        reminder_text = _clean_reminder_text(original)

        if not reminder_text:
            reminder_text = "Reminder"

        return ParsedReminder(
            text=reminder_text,
            remind_at=remind_at,
        )

    return None


# =============================================================
# COMPATIBILITY HELPERS
# =============================================================
#
# commands.py eski API nomlarini ishlatishi mumkin.
# Shu sababli ular mavjud bo‘lishi kerak.
#
# Asosiy reminder yaratish/bekor qilish ishlarini
# SchedulerManager bajaradi.
# =============================================================


async def create_reminder(
    *,
    owner_telegram_id: int,
    chat_id: int,
    text: str,
    remind_at: datetime,
):
    """
    Compatibility wrapper.

    Reminder yaratish uchun SchedulerManager ishlatiladi.
    """

    from app.scheduler.manager import scheduler_manager

    return await scheduler_manager.create_reminder(
        owner_telegram_id=owner_telegram_id,
        chat_id=chat_id,
        text=text,
        remind_at=remind_at,
    )


async def get_reminder_by_id(
    reminder_id: int,
    owner_telegram_id: int,
):
    """Compatibility wrapper."""

    from app.scheduler.manager import scheduler_manager

    return await scheduler_manager.get_reminder(
        reminder_id=reminder_id,
        owner_telegram_id=owner_telegram_id,
    )


async def cancel_reminder_by_id(
    reminder_id: int,
    owner_telegram_id: int,
) -> bool:
    """
    commands.py uchun eski API.

    Reminderni faqat uning egasi bekor qila oladi.
    """

    from app.scheduler.manager import scheduler_manager

    return await scheduler_manager.cancel_reminder(
        reminder_id=reminder_id,
        owner_telegram_id=owner_telegram_id,
    )


async def get_user_reminders(
    owner_telegram_id: int,
    *,
    include_completed: bool = False,
):
    """Foydalanuvchining reminderlarini olish."""

    from app.scheduler.manager import scheduler_manager

    return await scheduler_manager.get_user_reminders(
        owner_telegram_id,
        include_completed=include_completed,
    )


async def get_active_reminders():
    """Barcha aktiv reminderlarni olish."""

    from app.scheduler.manager import scheduler_manager

    return await scheduler_manager.get_active_reminders()


__all__ = [
    "ParsedReminder",
    "parse_reminder",
    "format_reminder_time",
    "create_reminder",
    "get_reminder_by_id",
    "cancel_reminder_by_id",
    "get_user_reminders",
    "get_active_reminders",
        ]
