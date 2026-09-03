from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config.settings import settings


# ============================================================
# REMINDER DATA
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


# ============================================================
# FORMAT TIME
# ============================================================

def format_reminder_time(dt: datetime) -> str:
    """
    Reminder vaqtini odamga tushunarli ko'rinishga keltiradi.
    """

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone())

    dt = dt.astimezone(_timezone())

    return dt.strftime("%d.%m.%Y %H:%M")


# ============================================================
# TEXT CLEANUP
# ============================================================

def _clean_reminder_text(text: str) -> str:
    """
    Reminder matnidan vaqt haqidagi qismini olib tashlaydi.
    """

    text = re.sub(
        r"\s+",
        " ",
        text,
        flags=re.UNICODE,
    ).strip()

    # Oxiridagi "eslat", "eslatib qo'y", "eslatib qo‘y"
    text = re.sub(
        r"\s+(?:menga\s+)?eslat(?:ib)?\s*(?:qo['’`]?y)?[.!]?$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s+(?:menga\s+)?eslat[.!]?$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip(" .,!?")


# ============================================================
# PARSE REMINDER
# ============================================================

def parse_reminder(text: str) -> ParsedReminder | None:
    """
    Uzbek tilidagi oddiy natural-language reminderlarni
    datetime'ga aylantiradi.

    Qo'llab-quvvatlanadi:

        10 daqiqadan keyin suv ichishni eslat
        1 soatdan keyin menga yozishni eslat
        30 minutdan keyin ...
        2 kundan keyin ...
        ertaga soat 10:00 da ...
        ertaga 10:00 da ...
        bugun 20:30 da ...
        soat 18:00 da ...
        18:00 da ...
    """

    if not text:
        return None

    original = str(text).strip()

    if not original:
        return None

    now = datetime.now(_timezone())

    # ========================================================
    # 1. "X DAQIQA / SOAT / KUN DAN KEYIN"
    # ========================================================

    relative_pattern = re.compile(
        r"^\s*"
        r"(?P<amount>\d+(?:[.,]\d+)?)"
        r"\s*"
        r"(?P<unit>"
        r"daqiqa|daqiqadan|"
        r"minut|minutdan|"
        r"soat|soatdan|"
        r"kun|kundan|"
        r"hafta|haftadan"
        r")"
        r"\s*"
        r"keyin"
        r"(?:\s+da)?"
        r"\s*"
        r"(?P<message>.*)"
        r"$",
        re.IGNORECASE,
    )

    match = relative_pattern.match(original)

    if match:
        amount = float(
            match.group("amount").replace(",", ".")
        )

        unit = match.group("unit").lower()
        message = match.group("message").strip()

        if "daqiqa" in unit or "minut" in unit:
            remind_at = now + timedelta(
                minutes=amount
            )

        elif "soat" in unit:
            remind_at = now + timedelta(
                hours=amount
            )

        elif "kun" in unit:
            remind_at = now + timedelta(
                days=amount
            )

        elif "hafta" in unit:
            remind_at = now + timedelta(
                weeks=amount
            )

        else:
            return None

        message = _clean_reminder_text(message)

        if not message:
            message = "Reminder"

        return ParsedReminder(
            text=message,
            remind_at=remind_at,
        )

    # ========================================================
    # 2. TIME EXTRACTOR
    # ========================================================

    time_pattern = re.compile(
        r"(?:"
        r"soat\s*"
        r")?"
        r"(?P<hour>\d{1,2})"
        r"[:.](?P<minute>\d{2})"
        r"(?:\s*(?P<ampm>am|pm))?"
        r"\s*(?:da)?",
        re.IGNORECASE,
    )

    time_match = time_pattern.search(original)

    # ========================================================
    # 3. "ERTAGA"
    # ========================================================

    if re.search(
        r"\bertaga\b",
        original,
        re.IGNORECASE,
    ):
        if time_match:
            hour = int(time_match.group("hour"))
            minute = int(time_match.group("minute"))

            ampm = time_match.group("ampm")

            if ampm:
                ampm = ampm.lower()

                if ampm == "pm" and hour < 12:
                    hour += 12

                if ampm == "am" and hour == 12:
                    hour = 0

            if hour > 23 or minute > 59:
                return None

            target_date = now.date() + timedelta(days=1)

            remind_at = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                hour,
                minute,
                tzinfo=_timezone(),
            )

            message = original[
                :time_match.start()
            ] + original[
                time_match.end():
            ]

            message = re.sub(
                r"\bertaga\b",
                "",
                message,
                flags=re.IGNORECASE,
            )

            message = _clean_reminder_text(message)

            if not message:
                message = "Reminder"

            return ParsedReminder(
                text=message,
                remind_at=remind_at,
            )

    # ========================================================
    # 4. "BUGUN"
    # ========================================================

    if re.search(
        r"\bbugun\b",
        original,
        re.IGNORECASE,
    ):
        if time_match:
            hour = int(time_match.group("hour"))
            minute = int(time_match.group("minute"))

            ampm = time_match.group("ampm")

            if ampm:
                ampm = ampm.lower()

                if ampm == "pm" and hour < 12:
                    hour += 12

                if ampm == "am" and hour == 12:
                    hour = 0

            if hour > 23 or minute > 59:
                return None

            remind_at = datetime(
                now.year,
                now.month,
                now.day,
                hour,
                minute,
                tzinfo=_timezone(),
            )

            # Agar bugungi vaqt o'tib ketgan bo'lsa,
            # ertaga deb olish.
            if remind_at <= now:
                remind_at += timedelta(days=1)

            message = (
                original[:time_match.start()]
                + original[time_match.end():]
            )

            message = re.sub(
                r"\bbugun\b",
                "",
                message,
                flags=re.IGNORECASE,
            )

            message = _clean_reminder_text(message)

            if not message:
                message = "Reminder"

            return ParsedReminder(
                text=message,
                remind_at=remind_at,
            )

    # ========================================================
    # 5. FAQAT "SOAT 18:00 DA ..."
    # ========================================================

    if time_match:
        hour = int(time_match.group("hour"))
        minute = int(time_match.group("minute"))

        ampm = time_match.group("ampm")

        if ampm:
            ampm = ampm.lower()

            if ampm == "pm" and hour < 12:
                hour += 12

            if ampm == "am" and hour == 12:
                hour = 0

        if hour > 23 or minute > 59:
            return None

        remind_at = datetime(
            now.year,
            now.month,
            now.day,
            hour,
            minute,
            tzinfo=_timezone(),
        )

        # Bugungi vaqt o'tib ketgan bo'lsa,
        # keyingi kun.
        if remind_at <= now:
            remind_at += timedelta(days=1)

        message = (
            original[:time_match.start()]
            + original[time_match.end():]
        )

        message = _clean_reminder_text(message)

        if not message:
            message = "Reminder"

        return ParsedReminder(
            text=message,
            remind_at=remind_at,
        )

    return None


__all__ = [
    "ParsedReminder",
    "parse_reminder",
    "format_reminder_time",
            ]
