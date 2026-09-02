from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.memory.manager import memory_manager
from app.scheduler.manager import scheduler_manager
from app.scheduler.reminders import (
    format_reminder_time,
    parse_reminder,
)


logger = logging.getLogger("sara.bot.commands")

router = Router(name="commands")


# ================================================================
# /START
# ================================================================

@router.message(Command("start"))
async def start_command(message: Message) -> None:

    await message.answer(
        "👋 Salom!\n\n"
        "Men <b>SARA AI</b>.\n"
        "Men suhbatni davom ettirish, xotirani saqlash "
        "va reminderlar bilan ishlashim mumkin.\n\n"
        "Masalan:\n"
        "• 10 daqiqadan keyin suv ichishni eslat\n"
        "• ertaga soat 09:00 da uchrashuvni eslat\n\n"
        "Yordam: /help",
        parse_mode="HTML",
    )


# ================================================================
# /HELP
# ================================================================

@router.message(Command("help"))
async def help_command(message: Message) -> None:

    await message.answer(
        "<b>SARA AI komandalar:</b>\n\n"

        "<b>Xotira:</b>\n"
        "/memory — xotiralarni ko‘rish\n"
        "/memory_stats — xotira statistikasi\n"
        "/forget ID — xotirani o‘chirish\n"
        "/memory_clear — barcha xotirani o‘chirish\n\n"

        "<b>Reminder:</b>\n"
        "/remind 10 daqiqadan keyin suv ichishni eslat\n"
        "/remind ertaga 09:00 uchrashuvni eslat\n"
        "/reminders — faol reminderlar\n"
        "/cancel_reminder ID — reminderni bekor qilish",
        parse_mode="HTML",
    )


# ================================================================
# /MEMORY
# ================================================================

@router.message(Command("memory"))
async def memory_command(message: Message) -> None:

    if not message.from_user:
        return

    memories = await memory_manager.get_user_memories(
        message.from_user.id,
        limit=30,
    )

    if not memories:
        await message.answer(
            "🧠 Hozircha saqlangan xotiralar yo‘q."
        )
        return

    lines = [
        "🧠 <b>Siz haqingizdagi xotiralar:</b>",
        "",
    ]

    for memory in memories:
        lines.append(
            f"#{memory.id} "
            f"[{memory.memory_type}] "
            f"{memory.content}\n"
            f"   Importance: {memory.importance}/100"
        )

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
    )


# ================================================================
# /MEMORY_STATS
# ================================================================

@router.message(Command("memory_stats"))
async def memory_stats_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    count = await memory_manager.user_memory_count(
        message.from_user.id
    )

    await message.answer(
        "🧠 <b>SARA Memory Stats</b>\n\n"
        f"Saqlangan xotiralar: <b>{count}</b>",
        parse_mode="HTML",
    )


# ================================================================
# /FORGET
# ================================================================

@router.message(Command("forget"))
async def forget_command(message: Message) -> None:

    if not message.from_user:
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Foydalanish:\n"
            "<code>/forget 12</code>",
            parse_mode="HTML",
        )
        return

    try:
        memory_id = int(parts[1].strip())
    except ValueError:
        await message.answer(
            "❌ Memory ID raqam bo‘lishi kerak."
        )
        return

    success = await memory_manager.forget_user_memory(
        user_telegram_id=message.from_user.id,
        memory_id=memory_id,
    )

    if success:
        await message.answer(
            f"🗑 Xotira #{memory_id} o‘chirildi."
        )
    else:
        await message.answer(
            f"❌ #{memory_id} xotira topilmadi."
        )


# ================================================================
# /MEMORY_CLEAR
# ================================================================

@router.message(Command("memory_clear"))
async def memory_clear_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    deleted = await memory_manager.clear_user_memories(
        message.from_user.id
    )

    await message.answer(
        f"🗑 {deleted} ta xotira o‘chirildi."
    )


# ================================================================
# /REMIND
# ================================================================

@router.message(Command("remind"))
async def remind_command(message: Message) -> None:
    """
    Misollar:

        /remind 10 daqiqadan keyin suv ichishni eslat

        /remind 2 soatdan keyin serverni tekshirishni eslat

        /remind ertaga 09:00 uchrashuvni eslat

        /remind bugun 20:30 filmni eslat
    """

    if not message.from_user:
        return

    parts = (message.text or "").split(
        maxsplit=1
    )

    if len(parts) < 2:
        await message.answer(
            "⏰ Reminder yaratish uchun:\n\n"
            "<code>/remind 10 daqiqadan keyin "
            "suv ichishni eslat</code>\n\n"
            "Yoki:\n"
            "<code>/remind ertaga 09:00 "
            "uchrashuvni eslat</code>",
            parse_mode="HTML",
        )
        return

    reminder_input = parts[1].strip()

    parsed = parse_reminder(
        reminder_input
    )

    if parsed is None:
        await message.answer(
            "❌ Vaqtni tushuna olmadim.\n\n"
            "Misollar:\n"
            "• 10 daqiqadan keyin suv ichishni eslat\n"
            "• 2 soatdan keyin serverni tekshir\n"
            "• ertaga 09:00 uchrashuvni eslat\n"
            "• bugun 20:30 filmni eslat"
        )
        return

    # Juda o'tmishga ketgan vaqtga yo'l qo'ymaslik
    if parsed.remind_at.timestamp() <= 0:
        await message.answer(
            "❌ Reminder vaqti noto‘g‘ri."
        )
        return

    try:
        reminder = await scheduler_manager.create_reminder(
            owner_telegram_id=message.from_user.id,
            chat_id=message.chat.id,
            text=parsed.text,
            remind_at=parsed.remind_at,
        )

    except Exception:
        logger.exception(
            "Failed to create reminder."
        )

        await message.answer(
            "❌ Reminder yaratishda xatolik yuz berdi."
        )
        return

    await message.answer(
        "✅ <b>Reminder yaratildi!</b>\n\n"
        f"📝 {reminder.text}\n"
        f"⏰ {format_reminder_time(reminder.remind_at)}\n"
        f"🆔 #{reminder.id}",
        parse_mode="HTML",
    )


# ================================================================
# /REMINDERS
# ================================================================

@router.message(Command("reminders"))
async def reminders_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    reminders = await scheduler_manager.get_user_reminders(
        owner_telegram_id=message.from_user.id
    )

    if not reminders:
        await message.answer(
            "⏰ Sizda faol reminderlar yo‘q."
        )
        return

    lines = [
        "⏰ <b>Sizning reminderlaringiz:</b>",
        "",
    ]

    for reminder in reminders:

        lines.append(
            f"🆔 <b>#{reminder.id}</b>\n"
            f"📝 {reminder.text}\n"
            f"⏰ {format_reminder_time(reminder.remind_at)}\n"
        )

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
    )


# ================================================================
# /CANCEL_REMINDER
# ================================================================

@router.message(Command("cancel_reminder"))
async def cancel_reminder_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    parts = (message.text or "").split(
        maxsplit=1
    )

    if len(parts) < 2:
        await message.answer(
            "Foydalanish:\n"
            "<code>/cancel_reminder 12</code>",
            parse_mode="HTML",
        )
        return

    try:
        reminder_id = int(
            parts[1].strip()
        )
    except ValueError:
        await message.answer(
            "❌ Reminder ID raqam bo‘lishi kerak."
        )
        return

    success = await scheduler_manager.cancel_reminder(
        reminder_id=reminder_id,
        owner_telegram_id=message.from_user.id,
    )

    if success:
        await message.answer(
            f"🗑 Reminder #{reminder_id} bekor qilindi."
        )
    else:
        await message.answer(
            f"❌ Reminder #{reminder_id} topilmadi "
            "yoki uni bekor qilib bo‘lmaydi."
  )
