from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agent.agent_context import agent_context_builder
from app.agent.emotional_state import emotional_state
from app.agent.loop_guard import loop_guard
from app.agent.proactive import proactive_agent
from app.services.privacy_service import privacy_service

logger = logging.getLogger("sara.agent.runtime")


# ============================================================
# AGENT RUNTIME CONTEXT
# ============================================================

@dataclass
class AgentRuntimeContext:
    """
    SARA Agent uchun bitta runtime session.

    Muhim:
    Orchestrator ushbu klassni runtime object sifatida ishlatadi.

    Shuning uchun:
        - prepare()
        - finalize()
        - build_agent_context()

    shu klass ichida mavjud.
    """

    chat_id: int
    user_id: int | None
    group_id: int | None

    is_private: bool
    is_group: bool

    is_bot_message: bool = False

    sara_called: bool = False
    is_reply_to_sara: bool = False
    is_question: bool = False

    proactive_allowed: bool = False

    agent_context: str = ""
    privacy_context: str = ""

    can_use_private_memory: bool = False
    can_use_group_memory: bool = False

    prepared: bool = False
    finalized: bool = False

    response_text: str = ""

    extra_flags: dict[str, Any] = field(
        default_factory=dict
    )

    # ========================================================
    # PREPARE
    # ========================================================

    async def prepare(
        self,
        *,
        user_text: str = "",
        extra_flags: dict[str, Any] | None = None,
    ) -> None:
        """
        Runtime sessionni tayyorlaydi.

        Orchestrator:
            await runtime.prepare(...)
        """

        self.extra_flags = dict(
            extra_flags or {}
        )

        # ----------------------------------------------------
        # FLAGS
        # ----------------------------------------------------

        self.is_question = bool(
            self.is_question
            or self.extra_flags.get(
                "is_question",
                False,
            )
        )

        self.proactive_allowed = bool(
            self.proactive_allowed
            or self.extra_flags.get(
                "proactive_allowed",
                False,
            )
        )

        self.is_bot_message = bool(
            self.is_bot_message
            or self.extra_flags.get(
                "is_bot_message",
                False,
            )
        )

        # ----------------------------------------------------
        # ACTIVITY
        # ----------------------------------------------------

        try:

            proactive_agent.record_activity(
                chat_id=self.chat_id
            )

        except Exception:

            logger.exception(
                "Could not record activity | chat=%s",
                self.chat_id,
            )

        # ----------------------------------------------------
        # LOOP GUARD
        # ----------------------------------------------------

        try:

            if not self.is_bot_message:

                loop_guard.register_user_message(
                    chat_id=self.chat_id
                )

        except Exception:

            logger.exception(
                "Could not register user message | chat=%s",
                self.chat_id,
            )

        # ----------------------------------------------------
        # EMOTIONAL STATE
        # ----------------------------------------------------

        if self.user_id is not None:

            try:

                if self.is_question:

                    emotional_state.update(
                        chat_id=self.chat_id,
                        user_id=self.user_id,
                        mood="curious",
                        intensity_change=0.05,
                        curiosity_change=0.08,
                    )

                elif self.sara_called:

                    emotional_state.update(
                        chat_id=self.chat_id,
                        user_id=self.user_id,
                        mood="engaged",
                        intensity_change=0.03,
                        curiosity_change=0.04,
                    )

                elif self.is_reply_to_sara:

                    emotional_state.update(
                        chat_id=self.chat_id,
                        user_id=self.user_id,
                        mood="engaged",
                        intensity_change=0.03,
                        curiosity_change=0.04,
                    )

                else:

                    emotional_state.update(
                        chat_id=self.chat_id,
                        user_id=self.user_id,
                        mood="neutral",
                        intensity_change=0.01,
                        curiosity_change=0.01,
                    )

            except Exception:

                logger.exception(
                    "Emotional state update failed | chat=%s",
                    self.chat_id,
                )

        # ----------------------------------------------------
        # PRIVACY
        # ----------------------------------------------------

        try:

            self.can_use_private_memory = bool(
                privacy_service.is_private_context(
                    group_id=self.group_id
                )
            )

        except Exception:

            logger.exception(
                "Privacy context check failed | chat=%s",
                self.chat_id,
            )

            self.can_use_private_memory = (
                self.is_private
            )

        self.can_use_group_memory = bool(
            self.group_id is not None
            or self.is_group
        )

        # ----------------------------------------------------
        # PRIVACY DESCRIPTION
        # ----------------------------------------------------

        if self.is_private:

            self.privacy_context = (
                "PRIVATE CONTEXT.\n"
                "SARA private user memory ishlatishi mumkin.\n"
                "Private memory boshqa foydalanuvchilarga "
                "oshkor qilinmasligi kerak."
            )

        else:

            self.privacy_context = (
                "GROUP CONTEXT.\n"
                "PRIVATE USER MEMORY HIDDEN.\n"
                "Private user memory guruhga olib chiqilmaydi.\n"
                "Faqat group memory va guruhdagi umumiy "
                "kontekst ishlatilishi mumkin."
            )

        # ----------------------------------------------------
        # AGENT CONTEXT
        # ----------------------------------------------------

        if self.user_id is not None:

            try:

                self.agent_context = (
                    await agent_context_builder.build(
                        chat_id=self.chat_id,
                        user_id=self.user_id,
                    )
                )

            except Exception:

                logger.exception(
                    "Agent context build failed | chat=%s",
                    self.chat_id,
                )

                self.agent_context = (
                    "SARA AGENT CONTEXT\n"
                    "==================\n"
                    "Qo'shimcha agent context mavjud emas."
                )

        else:

            self.agent_context = (
                "SARA AGENT CONTEXT\n"
                "==================\n"
                "User context mavjud emas."
            )

        self.prepared = True

        logger.debug(
            "Runtime prepared | chat=%s | user=%s | "
            "group=%s | private=%s | group_mode=%s | bot=%s",
            self.chat_id,
            self.user_id,
            self.group_id,
            self.is_private,
            self.is_group,
            self.is_bot_message,
        )

    # ========================================================
    # BUILD AGENT CONTEXT
    # ========================================================

    def build_agent_context(self) -> dict[str, Any]:
        """
        Runtime holatini Brain uchun dictionaryga aylantiradi.
        """

        return {
            "agent_context": self.agent_context,
            "privacy_context": self.privacy_context,

            "can_use_private_memory": (
                self.can_use_private_memory
            ),

            "can_use_group_memory": (
                self.can_use_group_memory
            ),

            "is_private": self.is_private,
            "is_group": self.is_group,
            "is_bot_message": self.is_bot_message,

            "sara_called": self.sara_called,
            "is_reply_to_sara": self.is_reply_to_sara,
            "is_question": self.is_question,

            "proactive_allowed": (
                self.proactive_allowed
            ),

            **self.extra_flags,
        }

    # ========================================================
    # FINALIZE
    # ========================================================

    async def finalize(
        self,
        *,
        response_text: str = "",
        success: bool = False,
    ) -> None:
        """
        Agent pipeline tugagandan keyingi runtime cleanup.
        """

        self.response_text = str(
            response_text or ""
        ).strip()

        try:

            if self.response_text and success:

                loop_guard.register_response(
                    chat_id=self.chat_id
                )

                loop_guard.register_bot_message(
                    chat_id=self.chat_id
                )

                proactive_agent.record_response(
                    chat_id=self.chat_id
                )

        except Exception:

            logger.exception(
                "Runtime response registration failed | chat=%s",
                self.chat_id,
            )

        self.finalized = True

        logger.debug(
            "Runtime finalized | chat=%s | success=%s",
            self.chat_id,
            success,
        )


# ============================================================
# LEGACY / MESSAGE BASED RUNTIME
# ============================================================

class AgentRuntime:
    """
    Eski message-based runtime API.

    Bu klass boshqa qismlardagi mavjud kodlarni buzmaslik
    uchun saqlanadi.
    """

    async def prepare(
        self,
        *,
        message: Any,
        user_id: int,
        group_id: int | None = None,
        sara_called: bool = False,
        is_question: bool = False,
        is_reply_to_sara: bool = False,
    ) -> AgentRuntimeContext:

        chat_id = int(
            message.chat.id
        )

        is_private = bool(
            group_id is None
            and message.chat.type == "private"
        )

        is_group = bool(
            group_id is not None
            or message.chat.type
            in {"group", "supergroup"}
        )

        is_bot = bool(
            message.from_user
            and message.from_user.is_bot
        )

        context = AgentRuntimeContext(
            chat_id=chat_id,
            user_id=user_id,
            group_id=group_id,
            is_private=is_private,
            is_group=is_group,
            is_bot_message=is_bot,
            sara_called=sara_called,
            is_question=is_question,
            is_reply_to_sara=is_reply_to_sara,
            proactive_allowed=False,
        )

        await context.prepare(
            user_text=(
                message.text
                or message.caption
                or ""
            ),
            extra_flags={
                "source": "legacy_agent_runtime",
            },
        )

        return context

    def register_response(
        self,
        *,
        chat_id: int,
        bot_interaction: bool = False,
    ) -> None:

        try:

            loop_guard.register_response(
                chat_id=chat_id
            )

            loop_guard.register_bot_message(
                chat_id=chat_id
            )

            proactive_agent.record_response(
                chat_id=chat_id
            )

        except Exception:

            logger.exception(
                "Could not register legacy response | chat=%s",
                chat_id,
            )

    def can_respond(
        self,
        *,
        chat_id: int,
        is_bot_message: bool = False,
    ) -> bool:

        return bool(
            loop_guard.can_respond(
                chat_id=chat_id,
                is_bot_message=is_bot_message,
            )
        )

    def reset(
        self,
        *,
        chat_id: int,
    ) -> None:

        try:
            loop_guard.reset(
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                "Loop guard reset failed | chat=%s",
                chat_id,
            )

        try:
            proactive_agent.reset(
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                "Proactive reset failed | chat=%s",
                chat_id,
            )

        try:
            emotional_state.reset(
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                "Emotional state reset failed | chat=%s",
                chat_id,
            )

        logger.info(
            "Agent runtime reset | chat=%s",
            chat_id,
        )


# ============================================================
# GLOBAL RUNTIME
# ============================================================

agent_runtime = AgentRuntime()


__all__ = [
    "AgentRuntimeContext",
    "AgentRuntime",
    "agent_runtime",
                    ]
