from __future__ import annotations

import logging

from aiogram.types import Message

from app.agent.agent_context import agent_context_builder
from app.agent.emotional_state import emotional_state
from app.agent.loop_guard import loop_guard
from app.agent.proactive import proactive_agent
from app.services.privacy_service import privacy_service

logger = logging.getLogger("sara.agent.runtime")


class AgentRuntime:
    """
    SARA Agent Runtime.

    Agentning turli qismlarini bitta joyga birlashtiradi:

    - Emotional State
    - Relationship Context
    - Proactive Agent
    - LoopGuard
    - Privacy
    """

    async def prepare(
        self,
        *,
        message: Message,
        user_id: int,
        group_id: int | None = None,
        sara_called: bool = False,
        is_question: bool = False,
        is_reply_to_sara: bool = False,
    ) -> dict[str, object]:

        chat_id = message.chat.id

        # ====================================================
        # ACTIVITY
        # ====================================================

        proactive_agent.record_activity(
            chat_id=chat_id
        )

        loop_guard.register_user_message(
            chat_id=chat_id
        )

        # ====================================================
        # CONTEXT TYPE
        # ====================================================

        is_private = group_id is None

        # ====================================================
        # EMOTIONAL STATE
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
                "Emotional state update failed."
            )

        # ====================================================
        # AGENT CONTEXT
        # ====================================================

        try:

            agent_context = await agent_context_builder.build(
                chat_id=chat_id,
                user_id=user_id,
            )

        except Exception:

            logger.exception(
                "Agent context build failed."
            )

            agent_context = (
                "SARA AGENT CONTEXT\n"
                "==================\n"
                "Qo'shimcha agent context mavjud emas."
            )

        # ====================================================
        # PRIVACY
        # ====================================================

        private_memory_allowed = (
            privacy_service.is_private_context(
                group_id=group_id
            )
        )

        if not private_memory_allowed:

            privacy_note = (
                "PRIVATE USER MEMORY HIDDEN.\n"
                "Guruh contextida private user "
                "memory ishlatilmaydi."
            )

        else:

            privacy_note = (
                "PRIVATE CONTEXT.\n"
                "User memory ishlatilishi mumkin."
            )

        # ====================================================
        # RETURN
        # ====================================================

        return {
            "chat_id": chat_id,
            "user_id": user_id,
            "group_id": group_id,
            "is_private": is_private,
            "sara_called": sara_called,
            "is_question": is_question,
            "is_reply_to_sara": is_reply_to_sara,
            "agent_context": agent_context,
            "privacy_context": privacy_note,
        }


agent_runtime = AgentRuntime()
