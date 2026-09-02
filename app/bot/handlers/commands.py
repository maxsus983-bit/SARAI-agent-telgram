from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.memory.manager import memory_manager


router = Router(name="commands")


@router.message(Command("start"))
async def start_command(
    message: Message,
) -> None:

    await message.answer(
        "Salom 👋\n\n"
        "Men SARA AI.\n"
        "Menga yozishing mumkin."
    )


@router.message(Command("help"))
async def help_command(
    message: Message,
) -> None:

    await message.answer(
        "🤖 SARA AI\n\n"
        "Menga oddiy xabar yoz — javob beraman.\n\n"
        "🧠 Xotira:\n"
        "/memory — xotiralarim\n"
        "/memory_stats — xotira statistikasi\n"
        "/forget <ID> — xotirani o'chirish\n"
        "/memory_clear — barcha xotirani o'chirish"
    )


@router.message(Command("memory"))
async def memory_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    memories = await memory_manager.get_user_memories(
        user_telegram_id=message.from_user.id,
        limit=30,
    )

    if not memories:

        await message.answer(
            "🧠 Hozircha sen haqingda "
            "saqlangan xotira yo'q."
        )

        return

    lines = [
        "🧠 SARA xotirasi:\n"
    ]

    for memory in memories:

        lines.append(
            f"#{memory.id} — "
            f"[{memory.memory_type}]\n"
            f"{memory.content}\n"
            f"⭐ {memory.importance}"
        )

    await message.answer(
        "\n\n".join(lines)
    )


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
        f"🧠 Saqlangan xotiralar: {count}"
    )


@router.message(Command("forget"))
async def forget_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:

        await message.answer(
            "Foydalanish:\n"
            "/forget 12"
        )

        return

    try:
        memory_id = int(parts[1])

    except ValueError:

        await message.answer(
            "❌ Xotira ID raqam bo'lishi kerak."
        )

        return

    success = await memory_manager.forget_user_memory(
        user_telegram_id=message.from_user.id,
        memory_id=memory_id,
    )

    if success:

        await message.answer(
            "✅ Xotira o'chirildi."
        )

    else:

        await message.answer(
            "❌ Bunday xotira topilmadi."
        )


@router.message(Command("memory_clear"))
async def memory_clear_command(
    message: Message,
) -> None:

    if not message.from_user:
        return

    deleted = await memory_manager.clear_user_memories(
        user_telegram_id=message.from_user.id
    )

    await message.answer(
        f"🗑️ {deleted} ta xotira o'chirildi."
  )
