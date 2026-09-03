from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot, Router
from aiogram.types import Message

from app.agent.telegram_bridge import process_group_message
from app.services.group_service import group_service
from app.services.message_service import message_service
from app.services.user_service import user_service

logger = logging.getLogger("sara.bot.groups")

router = Router(name="groups")


def _get_text(message: Message) -> str:
    """
    Telegram xabaridan ishlatiladigan matnni oladi.

    Hozircha text va caption qo'llab-quvvatlanadi.
    Media handlerlar keyinroq media ma'lumotlarini ham
    agent pipeline'iga uzatishi mumkin.
    """
    text = message.text or message.caption or ""
    return str(text).strip()


def _is_reply_to_sara(message: Message, bot: Bot) -> bool:
    """
    Xabar SARA yuborgan xabarga reply ekanligini aniqlaydi.
    """
    reply = message.reply_to_message

    if reply is None:
        return False

    if reply.from_user is None:
        return False

    if not reply.from_user.is_bot:
        return False

    if bot.id is None:
        return False

    return int(reply.from_user.id) == int(bot.id)


async def _save_user(message: Message) -> Any:
    """
    Telegram foydalanuvchisini DB'da yaratadi yoki yangilaydi.
    """
    if message.from_user is None:
        return None

    user = message.from_user

    return await user_service.get_or_create_user(
        telegram_id=int(user.id),
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language=user.language_code,
        is_bot=bool(user.is_bot),
    )


async def _save_group(message: Message) -> Any:
    """
    Guruhni DB'da yaratadi yoki yangilaydi.

    Muhim:
    Admin hech qanday /enable yoki /start command berishi shart emas.
    Guruhga SARA qo'shilishi bilan guruh avtomatik ravishda
    kuzatuv va agent pipeline'iga kiradi.
    """
    chat = message.chat

    return await group_service.get_or_create_group(
        telegram_id=int(chat.id),
        title=chat.title or "",
        username=getattr(chat, "username", None),
    )


async def _save_message(message: Message, text: str) -> Any:
    """
    Guruhdagi har bir matnli xabarni conversation history'ga saqlaydi.
    """
    if message.from_user is None:
        return None

    return await message_service.save_message(
        telegram_message_id=int(message.message_id),
        chat_id=int(message.chat.id),
        user_telegram_id=int(message.from_user.id),
        role="user",
        content=text,
        message_type="text",
        reply_to_message_id=(
            int(message.reply_to_message.message_id)
            if message.reply_to_message is not None
            else None
        ),
        is_bot_message=bool(message.from_user.is_bot),
    )


async def _save_bot_response(
    message: Message,
    response_text: str,
) -> Any:
    """
    SARA yuborgan javobni conversation history'ga saqlaydi.
    """
    return await message_service.save_message(
        telegram_message_id=0,
        chat_id=int(message.chat.id),
        user_telegram_id=None,
        role="assistant",
        content=response_text,
        message_type="text",
        reply_to_message_id=int(message.message_id),
        is_bot_message=True,
    )


def _was_already_sent(result: Any) -> bool:
    """
    Executor Telegram Tool orqali javobni allaqachon yuborgan bo'lsa,
    handler ikkinchi marta yubormasligi uchun tekshiradi.
    """
    try:
        agent_result = getattr(result, "agent_result", None)

        if agent_result is None:
            return False

        execution = getattr(agent_result, "execution", None)

        if execution is None:
            return False

        metadata = getattr(execution, "metadata", None)

        if not isinstance(metadata, dict):
            return False

        return bool(metadata.get("telegram_sent", False))

    except Exception:
        return False


@router.message()
async def handle_group_message(message: Message, bot: Bot) -> None:
    """
    Guruhdagi asosiy SARA handler.

    Har bir xabar:
        Telegram
          ↓
        User/Group DB
          ↓
        Conversation History
          ↓
        Agent Runtime
          ↓
        Brain
          ↓
        Memory Retrieval
          ↓
        Planner
          ↓
        Executor
          ↓
        Telegram

    Brain o'zi qaror qiladi:
      - javob berish
      - jim turish
      - savol berish
      - xotiraga saqlash
      - reminder
      - tool ishlatish
      - proactive javob
    """
    if message.chat.type not in {"group", "supergroup"}:
        return

    if message.from_user is None:
        return

    text = _get_text(message)

    # Media yoki bo'sh service-message bo'lsa,
    # media handlerlar uchun boshqa pipeline ishlashi mumkin.
    if not text:
        return

    try:
        # ---------------------------------------------------------
        # 1. USER
        # ---------------------------------------------------------
        await _save_user(message)

        # ---------------------------------------------------------
        # 2. GROUP
        # ---------------------------------------------------------
        await _save_group(message)

        # ---------------------------------------------------------
        # 3. RAW CONVERSATION HISTORY
        # ---------------------------------------------------------
        await _save_message(message, text)

        # ---------------------------------------------------------
        # 4. SARA'GA XABAR
        # ---------------------------------------------------------
        reply_to_sara = _is_reply_to_sara(message, bot)

        result = await process_group_message(
            message,
            text=text,
            sara_called=False,
            is_reply_to_sara=reply_to_sara,
            proactive_allowed=True,
            extra_flags={
                "source": "telegram_group_handler",
                "source_message_id": int(message.message_id),
                "telegram_message_id": int(message.message_id),
                "chat_id": int(message.chat.id),
                "chat_type": str(message.chat.type),
                "user_id": int(message.from_user.id),
                "group_id": int(message.chat.id),

                # MEMORY POLICY:
                # Guruhda user memory ishlatilishi mumkin.
                "use_user_memory": True,
                "use_group_memory": True,
                "use_conversation_memory": True,

                # SARA guruhda avtomatik faol bo'lishi mumkin.
                "autonomous_group_mode": True,
                "group_auto_enabled": True,
            },
        )

        if not getattr(result, "success", False):
            error = getattr(result, "error", None)

            if error:
                logger.warning(
                    "SARA group processing failed | chat=%s | error=%s",
                    message.chat.id,
                    error,
                )

            return

        should_send = bool(getattr(result, "should_send", False))
        response_text = str(
            getattr(result, "response_text", "") or ""
        ).strip()

        if not should_send or not response_text:
            return

        # ---------------------------------------------------------
        # 5. AGENT EXECUTOR TELEGRAM TOOL ORQALI YUBORGAN BO'LSA
        # ---------------------------------------------------------
        if _was_already_sent(result):
            return

        # ---------------------------------------------------------
        # 6. FALLBACK TELEGRAM SEND
        #
        # Bu faqat Executor Telegram Tool javob yubormagan bo'lsa
        # ishlaydi.
        # ---------------------------------------------------------
        sent = await bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            reply_to_message_id=message.message_id,
        )

        # ---------------------------------------------------------
        # 7. SARA JAVOBINI HISTORY'GA SAQLASH
        # ---------------------------------------------------------
        await message_service.save_message(
            telegram_message_id=int(sent.message_id),
            chat_id=int(message.chat.id),
            user_telegram_id=None,
            role="assistant",
            content=response_text,
            message_type="text",
            reply_to_message_id=int(message.message_id),
            is_bot_message=True,
        )

        logger.info(
            "SARA group response sent | chat=%s | message=%s",
            message.chat.id,
            sent.message_id,
        )

    except Exception:
        logger.exception(
            "Unhandled group handler error | chat=%s",
            message.chat.id,
        )


__all__ = ["router"]
