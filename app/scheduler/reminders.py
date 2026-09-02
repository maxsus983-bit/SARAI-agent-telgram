from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config.settings import settings


# ================================================================
# REMINDER PARSE RESULT
# ================================================================


@dataclass
class ReminderParseResult:
    """
    Reminder parser natijasi.
    """

    text: str
    remind_at: datetime


# ================================================================
# TIMEZONE
# ================================================================


def get_timezone() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


# ================================================================
# HELPERS
# ================================================================


def _make_future_time(
    *,
    amount: int,
    unit: str,
    now: datetime,
) -> datetime:
    """
    '10 daqiqadan keyin'
    '2 soatdan keyin'
    kabi vaqtlarni hisoblaydi.
    """

    unit = unit.lower()

    if unit in {
        "sekund",
        "sekunddan",
        "second",
        "seconds",
        "soniya",
    }:
        return now + timedelta(seconds=amount)

    if unit in {
        "minut",
        "minute",
        "minutes",
        "min",
        "daqiq",
        "daqiqa",
        "daqiqadan",
    }:
        return now + timedelta(minutes=amount)

    if unit in {
        "soat",
        "hour",
        "hours",
        "hr",
    }:
        return now + timedelta(hours=amount)

    if unit in {
        "kun",
        "day",
        "days",
    }:
        return now + timedelta(days=amount)

    if unit in {
        "hafta",
        "week",
        "weeks",
    }:
        return now + timedelta(weeks=amount)

    raise ValueError(f"Noma'lum vaqt birligi: {unit}")


def _parse_clock_time(
    hour: int,
    minute: int,
    now: datetime,
) -> datetime:
    """
    Bugungi soat:minutni datetimega aylantiradi.
    """

    result = now.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    return result


# ================================================================
# EXTRACT REMINDER TEXT
# ================================================================


def _clean_reminder_text(text: str) -> str:
    """
    Reminder gapidan vaqtga oid qismlarni olib tashlaydi.

    Misol:

        '10 daqiqadan keyin suv ichishni eslat'

    ->

        'suv ichishni eslat'
    """

    cleaned = text.strip()

    patterns = [
        # --------------------------------------------------------
        # Relative time
        # --------------------------------------------------------

        r"\b\d+\s*(?:sekund|soniya)(?:dan)?\s*keyin\b",
        r"\b\d+\s*(?:sekund|soniya)\s*dan\s*keyin\b",

        r"\b\d+\s*(?:minut|minute|minutes|min|daqiqa|daqiq)(?:dan)?\s*keyin\b",
        r"\b\d+\s*(?:minut|minute|minutes|min|daqiqa|daqiq)\s*dan\s*keyin\b",

        r"\b\d+\s*(?:soat|hour|hours|hr)(?:dan)?\s*keyin\b",
        r"\b\d+\s*(?:soat|hour|hours|hr)\s*dan\s*keyin\b",

        r"\b\d+\s*(?:kun|day|days)(?:dan)?\s*keyin\b",
        r"\b\d+\s*(?:kun|day|days)\s*dan\s*keyin\b",

        r"\b\d+\s*(?:hafta|week|weeks)(?:dan)?\s*keyin\b",
        r"\b\d+\s*(?:hafta|week|weeks)\s*dan\s*keyin\b",

        # --------------------------------------------------------
        # Today / tomorrow + clock
        # --------------------------------------------------------

        r"\bbugun\s+(?:soat\s*)?\d{1,2}(?::|\.)\d{2}\b",
        r"\bertaga\s+(?:soat\s*)?\d{1,2}(?::|\.)\d{2}\b",

        # --------------------------------------------------------
        # Reminder words
        # --------------------------------------------------------

        r"^\s*(?:menga\s+)?",
        r"\s*(?:eslat|eslatib\s+qo['’]?y|eslatib\s+qo['’]?ying)\s*$",
    ]

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Ba'zi tabiiy gaplarda "menga" o'rtada qolishi mumkin.
    cleaned = re.sub(
        r"^\s*menga\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


# ================================================================
# RELATIVE TIME PARSER
# ================================================================


def _parse_relative(
    text: str,
    now: datetime,
) -> ReminderParseResult | None:
    """
    Quyidagilarni tushunadi:

        10 daqiqadan keyin ...
        10 minutdan keyin ...
        2 soatdan keyin ...
        1 kundan keyin ...
        2 haftadan keyin ...
    """

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

    # Unitni standart ko'rinishga o'tkazish.
    if "sekund" in unit or "soniya" in unit:
        normalized_unit = "sekund"

    elif (
        "minut" in unit
        or "minute" in unit
        or unit.startswith("min")
        or "daqiqa" in unit
        or "daqiq" in unit
    ):
        normalized_unit = "minut"

    elif (
        "soat" in unit
        or "hour" in unit
        or unit == "hr"
        or unit.startswith("hr")
    ):
        normalized_unit = "soat"

    elif "kun" in unit or "day" in unit:
        normalized_unit = "kun"

    elif "hafta" in unit or "week" in unit:
        normalized_unit = "hafta"

    else:
        return None

    remind_at = _make_future_time(
        amount=amount,
        unit=normalized_unit,
        now=now,
    )

    reminder_text = _clean_reminder_text(text)

    if not reminder_text:
        reminder_text = "Reminder vaqti keldi."

    return ReminderParseResult(
        text=reminder_text,
        remind_at=remind_at,
    )


# ================================================================
# CLOCK PARSER
# ================================================================


def _parse_clock(
    text: str,
    now: datetime,
) -> ReminderParseResult | None:
    """
    Bugun/ertaga soat HH:MM formatini tushunadi.

    Misollar:

        bugun 20:30 da kino ko'rishni eslat
        ertaga soat 09:00 da uyg'onishni eslat
    """

    pattern = re.compile(
        r"""
        (?P<day>bugun|ertaga)
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

    if hour > 23 or minute > 59:
        return None

    remind_at = _parse_clock_time(
        hour=hour,
        minute=minute,
        now=now,
    )

    if day == "ertaga":
        remind_at += timedelta(days=1)

    # "bugun 08:00" deyilgan bo'lsa, lekin hozir 10:00 bo'lsa,
    # uni o'tgan vaqt sifatida qoldirmaymiz.
    elif day == "bugun" and remind_at <= now:
        remind_at += timedelta(days=1)

    reminder_text = _clean_reminder_text(text)

    if not reminder_text:
        reminder_text = "Reminder vaqti keldi."

    return ReminderParseResult(
        text=reminder_text,
        remind_at=remind_at,
    )


# ================================================================
# NATURAL REMINDER PARSER
# ================================================================


def parse_reminder(
    text: str,
    now: datetime | None = None,
) -> ReminderParseResult | None:
    """
    Oddiy tabiiy reminder gapini parse qiladi.

    Qo'llab-quvvatlanadi:

        10 daqiqadan keyin suv ichishni eslat

        30 minutdan keyin serverni tekshirishni eslat

        2 soatdan keyin menga yozishni eslat

        ertaga soat 09:00 da uchrashuvni eslat

        bugun 20:30 da filmni eslat
    """

    if not text or not text.strip():
        return None

    timezone = get_timezone()

    if now is None:
        now = datetime.now(timezone)

    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone)

    # ------------------------------------------------------------
    # 1. Relative time
    # ------------------------------------------------------------

    relative = _parse_relative(
        text=text,
        now=now,
    )

    if relative is not None:
        return relative

    # ------------------------------------------------------------
    # 2. Clock time
    # ------------------------------------------------------------

    clock = _parse_clock(
        text=text,
        now=now,
    )

    if clock is not None:
        return clock

    return None


# ================================================================
# FORMAT
# ================================================================


def format_reminder_time(
    remind_at: datetime,
) -> str:
    """
    Reminder vaqtini odamga tushunarli ko'rinishga keltiradi.
    """

    timezone = get_timezone()

    if remind_at.tzinfo is None:
        remind_at = remind_at.replace(
            tzinfo=timezone
        )

    local_time = remind_at.astimezone(timezone)

    return local_time.strftime(
        "%d.%m.%Y %H:%M"
)
