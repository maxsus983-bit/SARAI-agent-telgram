from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config.settings import settings


@dataclass
class ReminderParseResult:
    text: str
    remind_at: datetime


def get_timezone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


# ================================================================
# TEXT CLEANER
# ================================================================

def clean_reminder_text(text: str) -> str:
    """
    Reminder gapidan vaqt qismini olib tashlaydi.

    Misol:

        10 daqiqadan keyin suv ichishni eslat

    Natija:

        suv ichishni
    """

    cleaned = text.strip()

    patterns = [
        # Relative time
        r"\b\d+\s*(?:sekund|soniya)\s*dan\s*keyin\b",
        r"\b\d+\s*(?:sekund|soniya)dan\s*keyin\b",

        r"\b\d+\s*(?:minut|minute|minutes|min|daqiqa|daqiq)\s*dan\s*keyin\b",
        r"\b\d+\s*(?:minut|minute|minutes|min|daqiqa|daqiq)dan\s*keyin\b",

        r"\b\d+\s*(?:soat|hour|hours|hr)\s*dan\s*keyin\b",
        r"\b\d+\s*(?:soat|hour|hours|hr)dan\s*keyin\b",

        r"\b\d+\s*(?:kun|day|days)\s*dan\s*keyin\b",
        r"\b\d+\s*(?:kun|day|days)dan\s*keyin\b",

        r"\b\d+\s*(?:hafta|week|weeks)\s*dan\s*keyin\b",
        r"\b\d+\s*(?:hafta|week|weeks)dan\s*keyin\b",

        # Absolute date
        r"\bbugun\s+(?:soat\s*)?\d{1,2}[:.]\d{2}\b",
        r"\bertaga\s+(?:soat\s*)?\d{1,2}[:.]\d{2}\b",

        # Common reminder phrases
        r"^\s*menga\s+",
        r"^\s*iltimos\s+",
        r"\s+eslat(?:ib\s+qo['’]?y|ib\s+qo['’]?ying)?\s*$",
        r"\s+напомни\s*$",
        r"\s+remind\s+me\s*$",
    ]

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    ).strip()

    # Qolib ketgan "menga"
    cleaned = re.sub(
        r"^menga\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


# ================================================================
# RELATIVE TIME
# ================================================================

def parse_relative(
    text: str,
    now: datetime,
) -> ReminderParseResult | None:

    pattern = re.compile(
        r"""
        (?P<amount>\d+)
        \s*
        (?P<unit>
            sekund(?:dan)?
            |
            soniya(?:dan)?
            |
            minut(?:dan)?
            |
            minute(?:s)?(?:dan)?
            |
            min(?:dan)?
            |
            daqiqa(?:dan)?
            |
            daqiq(?:adan)?
            |
            soat(?:dan)?
            |
            hour(?:s)?(?:dan)?
            |
            hr(?:dan)?
            |
            kun(?:dan)?
            |
            day(?:s)?(?:dan)?
            |
            hafta(?:dan)?
            |
            week(?:s)?(?:dan)?
        )
        \s*
        keyin
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    match = pattern.search(text)

    if not match:
        return None

    amount = int(match.group("amount"))
    unit = match.group("unit").lower()

    if (
        "sekund" in unit
        or "soniya" in unit
    ):
        remind_at = now + timedelta(
            seconds=amount
        )

    elif (
        "minut" in unit
        or "minute" in unit
        or unit.startswith("min")
        or "daqiqa" in unit
        or "daqiq" in unit
    ):
        remind_at = now + timedelta(
            minutes=amount
        )

    elif (
        "soat" in unit
        or "hour" in unit
        or unit.startswith("hr")
    ):
        remind_at = now + timedelta(
            hours=amount
        )

    elif (
        "kun" in unit
        or "day" in unit
    ):
        remind_at = now + timedelta(
            days=amount
        )

    elif (
        "hafta" in unit
        or "week" in unit
    ):
        remind_at = now + timedelta(
            weeks=amount
        )

    else:
        return None

    reminder_text = clean_reminder_text(text)

    if not reminder_text:
        reminder_text = "Reminder vaqti keldi."

    return ReminderParseResult(
        text=reminder_text,
        remind_at=remind_at,
    )


# ================================================================
# ABSOLUTE CLOCK TIME
# ================================================================

def parse_clock(
    text: str,
    now: datetime,
) -> ReminderParseResult | None:

    pattern = re.compile(
        r"""
        (?P<day>bugun|ertaga|today|tomorrow)
        \s*
        (?:soat\s*)?
        (?P<hour>\d{1,2})
        \s*[:.]
        \s*
        (?P<minute>\d{2})
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    match = pattern.search(text)

    if not match:
        return None

    day = match.group("day").lower()

    hour = int(match.group("hour"))
    minute = int(match.group("minute"))

    if not 0 <= hour <= 23:
        return None

    if not 0 <= minute <= 59:
        return None

    remind_at = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    if day in {"ertaga", "tomorrow"}:
        remind_at += timedelta(days=1)

    elif day == "bugun" or day == "today":
        if remind_at <= now:
            remind_at += timedelta(days=1)

    reminder_text = clean_reminder_text(text)

    if not reminder_text:
        reminder_text = "Reminder vaqti keldi."

    return ReminderParseResult(
        text=reminder_text,
        remind_at=remind_at,
    )


# ================================================================
# MAIN PARSER
# ================================================================

def parse_reminder(
    text: str,
    now: datetime | None = None,
) -> ReminderParseResult | None:

    if not text or not text.strip():
        return None

    timezone = get_timezone()

    if now is None:
        now = datetime.now(timezone)

    elif now.tzinfo is None:
        now = now.replace(
            tzinfo=timezone
        )

    # 1. Relative
    result = parse_relative(
        text,
        now,
    )

    if result:
        return result

    # 2. Absolute clock
    result = parse_clock(
        text,
        now,
    )

    if result:
        return result

    return None


# ================================================================
# FORMATTER
# ================================================================

def format_reminder_time(
    remind_at: datetime,
) -> str:

    timezone = get_timezone()

    if remind_at.tzinfo is None:
        remind_at = remind_at.replace(
            tzinfo=timezone
        )

    local_time = remind_at.astimezone(
        timezone
    )

    return local_time.strftime(
        "%d.%m.%Y %H:%M"
)
