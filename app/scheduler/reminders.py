from __future__ import annotations

import logging
from typing import Any

from app.scheduler.reminders import (
    format_reminder_time,
    parse_reminder,
)
from app.scheduler.manager import scheduler_manager


logger = logging.getLogger("sara.agent.tools.reminder")


class ReminderTool:
    """
    SARA AI Reminder Tool.

    Vazifalari:

    - Natural language reminder yaratish
    - Reminderlarni ko'rish
    - Reminderni olish
    - Reminderni bekor qilish
    - Reminder vaqtini formatlash
    - Scheduler bilan ishlash
    """

    # ============================================================
    # CREATE
    # ============================================================

    async def create(
        self,
        *,
        owner_telegram_id: int,
        chat_id: int,
        text: str,
    ) -> dict[str, Any]:

        if not text or not text.strip():
            return {
                "success": False,
                "error": "Reminder matni bo'sh.",
            }

        parsed = parse_reminder(text)

        if parsed is None:
            return {
                "success": False,
                "error": (
                    "Reminder vaqtini tushunib bo'lmadi. "
                    "Masalan: '10 daqiqadan keyin suv ichishni eslat' "
                    "yoki 'ertaga soat 10:00 da uchrashuvni eslat'."
                ),
            }

        reminder = await scheduler_manager.create_reminder(
            owner_telegram_id=owner_telegram_id,
            chat_id=chat_id,
            text=parsed.text,
            remind_at=parsed.remind_at,
        )

        logger.info(
            "Reminder Tool create | id=%s | owner=%s | chat=%s",
            reminder.id,
            owner_telegram_id,
            chat_id,
        )

        return {
            "success": True,
            "operation": "create",
            "reminder_id": reminder.id,
            "owner_telegram_id": owner_telegram_id,
            "chat_id": chat_id,
            "text": reminder.text,
            "remind_at": reminder.remind_at.isoformat(),
            "formatted_time": format_reminder_time(
                reminder.remind_at
            ),
        }

    # ============================================================
    # GET
    # ============================================================

    async def get(
        self,
        *,
        owner_telegram_id: int,
        reminder_id: int,
    ) -> dict[str, Any]:

        reminder = await scheduler_manager.get_reminder(
            reminder_id=reminder_id,
            owner_telegram_id=owner_telegram_id,
        )

        if reminder is None:
            return {
                "success": False,
                "error": "Reminder topilmadi.",
            }

        return {
            "success": True,
            "operation": "get",
            "reminder_id": reminder.id,
            "owner_telegram_id": reminder.owner_telegram_id,
            "chat_id": reminder.chat_id,
            "text": reminder.text,
            "remind_at": reminder.remind_at.isoformat(),
            "formatted_time": format_reminder_time(
                reminder.remind_at
            ),
            "completed": reminder.completed,
            "cancelled": reminder.cancelled,
        }

    # ============================================================
    # LIST
    # ============================================================

    async def list(
        self,
        *,
        owner_telegram_id: int,
        include_completed: bool = False,
    ) -> dict[str, Any]:

        reminders = await scheduler_manager.get_user_reminders(
            owner_telegram_id=owner_telegram_id,
            include_completed=include_completed,
        )

        items = []

        for reminder in reminders:
            items.append(
                {
                    "id": reminder.id,
                    "chat_id": reminder.chat_id,
                    "text": reminder.text,
                    "remind_at": reminder.remind_at.isoformat(),
                    "formatted_time": format_reminder_time(
                        reminder.remind_at
                    ),
                    "completed": reminder.completed,
                    "cancelled": reminder.cancelled,
                }
            )

        return {
            "success": True,
            "operation": "list",
            "count": len(items),
            "reminders": items,
        }

    # ============================================================
    # CANCEL
    # ============================================================

    async def cancel(
        self,
        *,
        owner_telegram_id: int,
        reminder_id: int,
    ) -> dict[str, Any]:

        success = await scheduler_manager.cancel_reminder(
            reminder_id=reminder_id,
            owner_telegram_id=owner_telegram_id,
        )

        if not success:
            return {
                "success": False,
                "error": (
                    "Reminder bekor qilinmadi. "
                    "U mavjud emas, allaqachon bajarilgan "
                    "yoki allaqachon bekor qilingan bo'lishi mumkin."
                ),
            }

        return {
            "success": True,
            "operation": "cancel",
            "reminder_id": reminder_id,
        }


# ================================================================
# GLOBAL INSTANCE
# ================================================================

reminder_tool = ReminderTool()


# ================================================================
# TOOL HANDLER
# ================================================================

async def reminder_tool_handler(
    operation: str,
    **kwargs: Any,
) -> dict[str, Any]:

    operation = str(operation).strip().lower()

    if operation == "create":
        return await reminder_tool.create(
            owner_telegram_id=int(
                kwargs["owner_telegram_id"]
            ),
            chat_id=int(
                kwargs["chat_id"]
            ),
            text=str(
                kwargs["text"]
            ),
        )

    if operation == "get":
        return await reminder_tool.get(
            owner_telegram_id=int(
                kwargs["owner_telegram_id"]
            ),
            reminder_id=int(
                kwargs["reminder_id"]
            ),
        )

    if operation == "list":
        return await reminder_tool.list(
            owner_telegram_id=int(
                kwargs["owner_telegram_id"]
            ),
            include_completed=bool(
                kwargs.get(
                    "include_completed",
                    False,
                )
            ),
        )

    if operation == "cancel":
        return await reminder_tool.cancel(
            owner_telegram_id=int(
                kwargs["owner_telegram_id"]
            ),
            reminder_id=int(
                kwargs["reminder_id"]
            ),
        )

    return {
        "success": False,
        "error": f"Noma'lum reminder operation: {operation}",
        }
