from __future__ import annotations

import logging
from dataclasses import dataclass

from aiogram.types import Message

from app.agent.agent_context import agent_context_builder
from app.agent.emotional_state import emotional_state
from app.agent.loop_guard import loop_guard
from app.agent.proactive import proactive_agent
from app.services.privacy_service import privacy_service

logger = logging.getLogger("sara.agent.runtime")


# ============================================================
# AGENT DECISION CONTEXT
# ============================================================

@dataclass
class AgentRuntimeContext:
    chat_id: int
    user_id: int
    group_id: int | None

    is_private: bool
    is_group: bool
    is_bot: bool

    sara_called: bool
    is_question: bool
    is_reply_to_sara: bool

    agent_context: str
    privacy_context: str

    can_use_private_memory: bool
    can_use_group_memory: bool


# ============================================================
# AGENT RUNTIME
# ============================================================

class AgentRuntime:

    async def prepare(
        self,
        *,
        message: Message,
        user_id: int,
        group_id: int | None = None,
        sara_called: bool = False,
        is_question: bool = False,
        is_reply_to_sara: bool = False,
    ) -> AgentRuntimeContext:

        chat_id = message.chat.id

        is_private = (
            group_id is None
            and message.chat.type == "private"
        )

        is_group = (
            group_id is not None
            or message.chat.type
            in {"group", "supergroup"}
        )

        is_bot = bool(
            message.from_user
            and message.from_user.is_bot
        )

        # ====================================================
        # ACTIVITY
        # ====================================================

        proactive_agent.record_activity(
            chat_id=chat_id
        )

        # ====================================================
        # LOOP STATE
        # ====================================================

        if not is_bot:
            loop_guard.register_user_message(
                chat_id=chat_id
            )

        # ====================================================
        # EMOTIONAL / SESSION STATE
        # ====================================================

        try:

            if is_question:

                emotional_state.update(
                    chat_id=chat_id,
                    user_id=user_id,
                    mood="curious",
                    intensity_change=0.05,
                    curiosity_change=0.08,
                )

            elif sara_called:

                emotional_state.update(
                    chat_id=chat_id,
                    user_id=user_id,
                    mood="engaged",
                    intensity_change=0.03,
                    curiosity_change=0.04,
                )

            elif is_reply_to_sara:

                emotional_state.update(
                    chat_id=chat_id,
                    user_id=user_id,
                    mood="engaged",
                    intensity_change=0.03,
                    curiosity_change=0.04,
                )

            else:

                emotional_state.update(
                    chat_id=chat_id,
                    user_id=user_id,
                    mood="neutral",
                    intensity_change=0.01,
                    curiosity_change=0.01,
                )

        except Exception:

            logger.exception(
                "Emotional state update failed | chat=%s",
                chat_id,
            )

        # ====================================================
        # PRIVACY
        # ====================================================

        can_use_private_memory = (
            privacy_service.is_private_context(
                group_id=group_id
            )
        )

        can_use_group_memory = (
            group_id is not None
        )

        if is_private:

            privacy_context = (
                "PRIVATE CONTEXT.\n"
                "SARA private user memory ishlatishi mumkin.\n"
                "Private memory boshqa foydalanuvchilarga "
                "oshkor qilinmasligi kerak."
            )

        else:

            privacy_context = (
                "GROUP CONTEXT.\n"
                "PRIVATE USER MEMORY HIDDEN.\n"
                "Private user memory guruhga olib chiqilmaydi.\n"
                "Faqat group memory va guruhdagi umumiy "
                "kontekst ishlatilishi mumkin."
            )

        # ====================================================
        # AGENT CONTEXT
        # ====================================================

        try:

            agent_context = (
                await agent_context_builder.build(
                    chat_id=chat_id,
                    user_id=user_id,
                )
            )

        except Exception:

            logger.exception(
                "Agent context build failed | chat=%s",
                chat_id,
            )

            agent_context = (
                "SARA AGENT CONTEXT\n"
                "==================\n"
                "Qo'shimcha agent context mavjud emas."
            )

        # ====================================================
        # RETURN
        # ====================================================

        return AgentRuntimeContext(
            chat_id=chat_id,
            user_id=user_id,
            group_id=group_id,

            is_private=is_private,
            is_group=is_group,
            is_bot=is_bot,

            sara_called=sara_called,
            is_question=is_question,
            is_reply_to_sara=is_reply_to_sara,

            agent_context=agent_context,
            privacy_context=privacy_context,

            can_use_private_memory=(
                can_use_private_memory
            ),

            can_use_group_memory=(
                can_use_group_memory
            ),
        )

    # ========================================================
    # RESPONSE
    # ========================================================

    def register_response(
        self,
        *,
        chat_id: int,
        bot_interaction: bool = False,
    ) -> None:

        loop_guard.register_response(
            chat_id=chat_id
        )

        loop_guard.register_bot_message(
            chat_id=chat_id
        )

        proactive_agent.record_response(
            chat_id=chat_id
        )

        logger.debug(
            "Agent response registered | chat=%s | bot_interaction=%s",
            chat_id,
            bot_interaction,
        )

    # ========================================================
    # SHOULD RESPOND
    # ========================================================

    def can_respond(
        self,
        *,
        chat_id: int,
        is_bot_message: bool = False,
    ) -> bool:

        return loop_guard.can_respond(
            chat_id=chat_id,
            is_bot_message=is_bot_message,
        )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        *,
        chat_id: int,
    ) -> None:

        loop_guard.reset(
            chat_id=chat_id
        )

        proactive_agent.reset(
            chat_id=chat_id
        )

        emotional_state.reset(
            chat_id=chat_id
        )

        logger.info(
            "Agent runtime reset | chat=%s",
            chat_id,
        )


# ============================================================
# GLOBAL AGENT RUNTIME
# ============================================================

agent_runtime = AgentRuntime()
