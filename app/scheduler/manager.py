from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from app.config.settings import settings
from app.database.models import Reminder
from app.database.session import SessionFactory


logger = logging.getLogger("sara.scheduler")


class SchedulerManager:
    """
    SARA AI Reminder Scheduler.

    Vazifalari:

    - Reminder yaratish
    - Reminderni DB ga saqlash
    - APScheduler orqali vaqtini kutish
    - Reminder vaqtida Telegramga yuborish
    - Reminderni completed qilish
    - Reminderni cancel qilish
    - Bot restart bo'lganda reminderlarni qayta tiklash
    """

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(
            timezone=ZoneInfo(settings.timezone)
        )

        self.bot: Bot | None = None

    # ============================================================
    # BOTNI ULASH
    # ============================================================

    def set_bot(self, bot: Bot) -> None:
        """
        Schedulerga Telegram Bot obyektini beradi.
        """

        self.bot = bot

        logger.info("Telegram Bot Schedulerga ulandi.")

    # ============================================================
    # START
    # ============================================================

    def start(self) -> None:
        """
        Schedulerni ishga tushiradi.
        """

        if self.scheduler.running:
            logger.warning("Scheduler allaqachon ishlayapti.")
            return

        self.scheduler.start()

        logger.info(
            "SARA Scheduler ishga tushdi | timezone=%s",
            settings.timezone,
        )

    # ============================================================
    # STOP
    # ============================================================

    async def stop(self) -> None:
        """
        Schedulerni to'xtatadi.
        """

        if not self.scheduler.running:
            return

        self.scheduler.shutdown(wait=False)

        logger.info("SARA Scheduler to'xtatildi.")

    # ============================================================
    # REMINDER YARATISH
    # ============================================================

    async def create_reminder(
        self,
        *,
        owner_telegram_id: int,
        chat_id: int,
        text: str,
        remind_at: datetime,
    ) -> Reminder:
        """
        Yangi reminder yaratadi.

        Muhim:

        1. Avval DB ga yoziladi.
        2. Keyin schedulerga qo'shiladi.

        Shu sababli bot restart bo'lsa ham reminder yo'qolmaydi.
        """

        # --------------------------------------------------------
        # Vaqtni timezone bilan tekshirish
        # --------------------------------------------------------

        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(
                tzinfo=ZoneInfo(settings.timezone)
            )

        # --------------------------------------------------------
        # DB ga saqlash
        # --------------------------------------------------------

        async with SessionFactory() as session:

            reminder = Reminder(
                owner_telegram_id=owner_telegram_id,
                chat_id=chat_id,
                text=text.strip(),
                remind_at=remind_at,
                completed=False,
                cancelled=False,
            )

            session.add(reminder)

            await session.commit()
            await session.refresh(reminder)

            reminder_id = reminder.id

        # --------------------------------------------------------
        # Schedulerga qo'shish
        # --------------------------------------------------------

        self.schedule_reminder(
            reminder_id=reminder_id,
            remind_at=remind_at,
        )

        logger.info(
            "Reminder yaratildi | id=%s | owner=%s | chat=%s | at=%s",
            reminder_id,
            owner_telegram_id,
            chat_id,
            remind_at.isoformat(),
        )

        return reminder

    # ============================================================
    # REMINDERNI SCHEDULERGA QO'SHISH
    # ============================================================

    def schedule_reminder(
        self,
        *,
        reminder_id: int,
        remind_at: datetime,
    ) -> None:
        """
        Mavjud reminderni APSchedulerga qo'shadi.
        """

        job_id = self._job_id(reminder_id)

        # Eski job mavjud bo'lsa olib tashlaymiz.
        existing_job = self.scheduler.get_job(job_id)

        if existing_job:
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self._execute_reminder,
            trigger=DateTrigger(
                run_date=remind_at,
                timezone=ZoneInfo(settings.timezone),
            ),
            id=job_id,
            args=[reminder_id],
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
            max_instances=1,
        )

        logger.debug(
            "Reminder schedulerga qo'shildi | id=%s | at=%s",
            reminder_id,
            remind_at.isoformat(),
        )

    # ============================================================
    # REMINDERNI BAJARISH
    # ============================================================

    async def _execute_reminder(
        self,
        reminder_id: int,
    ) -> None:
        """
        Reminder vaqti kelganda chaqiriladi.
        """

        logger.info(
            "Reminder bajarilmoqda | id=%s",
            reminder_id,
        )

        # --------------------------------------------------------
        # Bot mavjudligini tekshirish
        # --------------------------------------------------------

        if self.bot is None:
            logger.error(
                "Reminder bajarilmadi: Telegram Bot ulanmagan | id=%s",
                reminder_id,
            )
            return

        # --------------------------------------------------------
        # DB dan reminder olish
        # --------------------------------------------------------

        async with SessionFactory() as session:

            result = await session.execute(
                select(Reminder).where(
                    Reminder.id == reminder_id
                )
            )

            reminder = result.scalar_one_or_none()

            if reminder is None:
                logger.warning(
                    "Reminder DB da topilmadi | id=%s",
                    reminder_id,
                )
                return

            # ----------------------------------------------------
            # Already completed/cancelled?
            # ----------------------------------------------------

            if reminder.completed:
                logger.info(
                    "Reminder allaqachon bajarilgan | id=%s",
                    reminder_id,
                )
                return

            if reminder.cancelled:
                logger.info(
                    "Reminder bekor qilingan | id=%s",
                    reminder_id,
                )
                return

            # ----------------------------------------------------
            # Telegramga yuborish
            # ----------------------------------------------------

            try:
                await self.bot.send_message(
                    chat_id=reminder.chat_id,
                    text=(
                        "⏰ <b>SARA Reminder</b>\n\n"
                        f"{reminder.text}"
                    ),
                    parse_mode="HTML",
                )

            except Exception:
                logger.exception(
                    "Reminder Telegramga yuborilmadi | id=%s",
                    reminder_id,
                )

                # Telegram xatosida completed qilmaymiz.
                # Shunda keyinchalik recovery/retry mexanizmi
                # ishlashi mumkin.
                return

            # ----------------------------------------------------
            # Completed
            # ----------------------------------------------------

            reminder.completed = True

            await session.commit()

        logger.info(
            "Reminder muvaffaqiyatli bajarildi | id=%s",
            reminder_id,
        )

    # ============================================================
    # REMINDERNI BEKOR QILISH
    # ============================================================

    async def cancel_reminder(
        self,
        reminder_id: int,
        owner_telegram_id: int,
    ) -> bool:
        """
        Reminderni bekor qiladi.

        Faqat reminder egasi bekor qila oladi.
        """

        async with SessionFactory() as session:

            result = await session.execute(
                select(Reminder).where(
                    Reminder.id == reminder_id,
                    Reminder.owner_telegram_id == owner_telegram_id,
                )
            )

            reminder = result.scalar_one_or_none()

            if reminder is None:
                return False

            if reminder.completed:
                return False

            if reminder.cancelled:
                return False

            reminder.cancelled = True

            await session.commit()

        # APScheduler jobini olib tashlash
        job_id = self._job_id(reminder_id)

        existing_job = self.scheduler.get_job(job_id)

        if existing_job:
            self.scheduler.remove_job(job_id)

        logger.info(
            "Reminder bekor qilindi | id=%s | owner=%s",
            reminder_id,
            owner_telegram_id,
        )

        return True

    # ============================================================
    # BITTA REMINDERNI OLISH
    # ============================================================

    async def get_reminder(
        self,
        reminder_id: int,
        owner_telegram_id: int,
    ) -> Reminder | None:
        """
        Reminder egasiga tegishli reminderni qaytaradi.
        """

        async with SessionFactory() as session:

            result = await session.execute(
                select(Reminder).where(
                    Reminder.id == reminder_id,
                    Reminder.owner_telegram_id == owner_telegram_id,
                )
            )

            return result.scalar_one_or_none()

    # ============================================================
    # USER REMINDERLARI
    # ============================================================

    async def get_user_reminders(
        self,
        owner_telegram_id: int,
        *,
        include_completed: bool = False,
    ) -> list[Reminder]:
        """
        Foydalanuvchining reminderlarini qaytaradi.
        """

        async with SessionFactory() as session:

            query = select(Reminder).where(
                Reminder.owner_telegram_id == owner_telegram_id,
                Reminder.cancelled.is_(False),
            )

            if not include_completed:
                query = query.where(
                    Reminder.completed.is_(False)
                )

            query = query.order_by(
                Reminder.remind_at.asc()
            )

            result = await session.execute(query)

            return list(result.scalars().all())

    # ============================================================
    # BARCHA ACTIVE REMINDERLAR
    # ============================================================

    async def get_active_reminders(self) -> list[Reminder]:
        """
        Bot restartdan keyin hali bajarilmagan reminderlarni oladi.
        """

        async with SessionFactory() as session:

            result = await session.execute(
                select(Reminder)
                .where(
                    Reminder.completed.is_(False),
                    Reminder.cancelled.is_(False),
                )
                .order_by(Reminder.remind_at.asc())
            )

            return list(result.scalars().all())

    # ============================================================
    # REMINDER JOB ID
    # ============================================================

    @staticmethod
    def _job_id(reminder_id: int) -> str:
        return f"sara-reminder-{reminder_id}"


# ================================================================
# GLOBAL SCHEDULER
# ================================================================

scheduler_manager = SchedulerManager()
