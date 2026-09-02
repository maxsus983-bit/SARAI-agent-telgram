from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config.settings import settings
from app.scheduler.manager import scheduler_manager


logger = logging.getLogger("sara.scheduler.recovery")


async def restore_reminders() -> int:
    """
    Bot restart bo'lgandan keyin DB dagi barcha aktiv
    reminderlarni APSchedulerga qayta joylaydi.

    Natija:
        Bot o'chdi
        ↓
        Bot qayta ishga tushdi
        ↓
        SQLite/PostgreSQL'dan reminderlar o'qiladi
        ↓
        Schedulerga qayta qo'shiladi
    """

    reminders = await scheduler_manager.get_active_reminders()

    if not reminders:
        logger.info("Tiklanadigan reminder topilmadi.")
        return 0

    timezone = ZoneInfo(settings.timezone)

    restored = 0
    expired = 0

    now = datetime.now(timezone)

    for reminder in reminders:

        remind_at = reminder.remind_at

        # DB timezone'siz datetime qaytarsa,
        # Asia/Tashkent deb qabul qilamiz.
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(
                tzinfo=timezone
            )

        # --------------------------------------------------------
        # Kelajakdagi reminder
        # --------------------------------------------------------

        if remind_at > now:

            scheduler_manager.schedule_reminder(
                reminder_id=reminder.id,
                remind_at=remind_at,
            )

            restored += 1

            logger.info(
                "Reminder tiklandi | id=%s | at=%s",
                reminder.id,
                remind_at.isoformat(),
            )

        # --------------------------------------------------------
        # O'tib ketgan reminder
        # --------------------------------------------------------

        else:
            """
            Agar bot o'chib turgan paytda reminder vaqti o'tib ketgan
            bo'lsa, uni imkon qadar tez bajarish uchun hozirga
            schedule qilamiz.

            Masalan:

                Reminder: 10:00
                Bot o'chgan
                Bot: 10:30 da qaytdi

            Reminder yo'qolmaydi.
            U darhol yuboriladi.
            """

            scheduler_manager.schedule_reminder(
                reminder_id=reminder.id,
                remind_at=now,
            )

            expired += 1

            logger.info(
                "O'tib ketgan reminder qayta schedule qilindi | id=%s",
                reminder.id,
            )

    logger.info(
        "Reminder recovery tugadi | restored=%s | expired=%s",
        restored,
        expired,
    )

    return restored + expired
