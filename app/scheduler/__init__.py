"""
SARA AI Scheduler Package.

Bu package quyidagi vazifalarni boshqaradi:

- Reminder yaratish
- Reminderlarni vaqtida ishga tushirish
- Bot restart bo'lganda reminderlarni tiklash
- Persistent reminder storage
- Scheduler lifecycle
"""

from app.scheduler.manager import scheduler_manager


__all__ = [
    "scheduler_manager",
]
