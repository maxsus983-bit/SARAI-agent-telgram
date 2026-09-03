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
    """SARA AI Reminder Tool."""

    async def create(
        self,
        *,
        owner_telegram_id: int,
        chat_id: int,
        text: str,
    ) -> dict[str, Any]:

        text = str(text or "").strip()

        if not text:
            return {
                "success": False,
                "error": "Reminder matni bo'sh.",
            }

        try:
            parsed = parse_reminder(text)
        except Exception as exc:
            logger.exception("Reminder parsing failed.")
            return {
                "success": False,
                "error": f"Reminder vaqtini aniqlashda xato: {exc}",
            }

        if parsed is None:
            return {
                "success": False,
                "error": (
                    "Reminder vaqtini tushunib bo'lmadi. "
                    "Masalan: '10 daqiqadan keyin suv ichishni eslat' "
                    "yoki 'ertaga soat 10:00 da uchrashuvni eslat'."
                ),
            }

        try:
            reminder = await scheduler_manager.create_reminder(
                owner_telegram_id=owner_telegram_id,
                chat_id=chat_id,
                text=parsed.text,
                remind_at=parsed.remind_at,
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

        except Exception as exc:
            logger.exception("Reminder creation failed.")
            return {
                "success": False,
                "error": str(exc),
            }

    async def get(
        self,
        *,
        owner_telegram_id: int,
        reminder_id: int,
    ) -> dict[str, Any]:

        try:
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

        except Exception as exc:
            logger.exception("Reminder get failed.")
            return {
                "success": False,
                "error": str(exc),
            }

    async def list(
        self,
        *,
        owner_telegram_id: int,
        include_completed: bool = False,
    ) -> dict[str, Any]:

        try:
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

        except Exception as exc:
            logger.exception("Reminder list failed.")
            return {
                "success": False,
                "error": str(exc),
            }

    async def cancel(
        self,
        *,
        owner_telegram_id: int,
        reminder_id: int,
    ) -> dict[str, Any]:

        try:
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

        except Exception as exc:
            logger.exception("Reminder cancel failed.")
            return {
                "success": False,
                "error": str(exc),
            }


reminder_tool = ReminderTool()


async def reminder_tool_handler(
    operation: str,
    **kwargs: Any,
) -> dict[str, Any]:

    operation = str(operation or "").strip().lower()

    try:
        if operation == "create":
            return await reminder_tool.create(
                owner_telegram_id=int(kwargs["owner_telegram_id"]),
                chat_id=int(kwargs["chat_id"]),
                text=str(kwargs["text"]),
            )

        if operation == "get":
            return await reminder_tool.get(
                owner_telegram_id=int(kwargs["owner_telegram_id"]),
                reminder_id=int(kwargs["reminder_id"]),
            )

        if operation == "list":
            return await reminder_tool.list(
                owner_telegram_id=int(kwargs["owner_telegram_id"]),
                include_completed=bool(
                    kwargs.get("include_completed", False)
                ),
            )

        if operation == "cancel":
            return await reminder_tool.cancel(
                owner_telegram_id=int(kwargs["owner_telegram_id"]),
                reminder_id=int(kwargs["reminder_id"]),
            )

        return {
            "success": False,
            "error": f"Noma'lum reminder operation: {operation}",
        }

    except KeyError as exc:
        return {
            "success": False,
            "error": f"Kerakli parametr yo'q: {exc}",
        }

    except Exception as exc:
        logger.exception("Reminder tool handler failed.")
        return {
            "success": False,
            "error": str(exc),
        }


__all__ = [
    "ReminderTool",
    "reminder_tool",
    "reminder_tool_handler",
          ]
