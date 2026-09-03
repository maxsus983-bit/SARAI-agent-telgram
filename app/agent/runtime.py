from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from aiogram.types import Message

from app.agent.agent_context import agent_context_builder
from app.agent.emotional_state import emotional_state
from app.agent.loop_guard import loop_guard
from app.agent.proactive import proactive_agent
from app.services.privacy_service import privacy_service


logger = logging.getLogger("sara.agent.runtime")


@dataclass
class AgentRuntimeContext:
    """
    SARA AI Agent Runtime Context.

    Orchestrator bilan to'g'ridan-to'g'ri ishlaydi.
    """

    chat_id: int
    user_id: int

    group_id: int | None = None

    is_group: bool = False
    is_private: bool = True

    is_bot: bool = False
    is_bot_message: bool = False

    sara_called: bool = False
    is_question: bool = False
    is_reply_to_sara: bool = False

    proactive_allowed: bool = True

    agent_context: str = ""
    privacy_context: str = ""

    can_use_private_memory: bool = False
    can_use_group_memory: bool = False

    extra_flags: dict[str, Any] = field(
        default_factory=dict
    )

    prepared: bool = False
    finalized: bool = False

    async def prepare(
        self,
        *,
        user_text: str = "",
        extra_flags: dict[str, Any] | None = None,
    ) -> "AgentRuntimeContext":
        """
        Runtime contextni tayyorlaydi.
        """

        if extra_flags:
            self.extra_flags.update(extra_flags)

        # --------------------------------------------------
        # FLAGS
        # --------------------------------------------------

        if "is_question" in self.extra_flags:
            self.is_question = bool(
                self.extra_flags["is_question"]
            )

        if "sara_called" in self.extra_flags:
            self.sara_called = bool(
                self.extra_flags["sara_called"]
            )

        if "is_reply_to_sara" in self.extra_flags:
            self.is_reply_to_sara = bool(
                self.extra_flags["is_reply_to_sara"]
            )

        if "is_bot_message" in self.extra_flags:
            self.is_bot_message = bool(
                self.extra_flags["is_bot_message"]
            )

        if "proactive_allowed" in self.extra_flags:
            self.proactive_allowed = bool(
                self.extra_flags["proactive_allowed"]
            )

        # Agar Telegram message botdan kelgan bo'lsa
        if self.is_bot_message:
            self.is_bot = True

        # --------------------------------------------------
        # PROACTIVE ACTIVITY
        # --------------------------------------------------

        try:
            proactive_agent.record_activity(
                chat_id=self.chat_id
            )
        except Exception:
            logger.exception(
                "Could not record proactive activity."
            )

        # --------------------------------------------------
        # LOOP GUARD
        # --------------------------------------------------

        try:
            if not self.is_bot_message and not self.is_bot:
                loop_guard.register_user_message(
                    chat_id=self.chat_id
                )
        except Exception:
            logger.exception(
                "Could not register user message."
            )

        # --------------------------------------------------
        # EMOTIONAL STATE
        # --------------------------------------------------

        try:
            if self.is_question:
                emotional_state.update(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                    event="question",
                )

            elif self.sara_called:
                emotional_state.update(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                    event="mentioned",
                )

            elif self.is_reply_to_sara:
                emotional_state.update(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                    event="reply",
                )

            else:
                emotional_state.update(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                    event="message",
                )

        except Exception:
            logger.exception(
                "Could not update emotional state."
            )

        # --------------------------------------------------
        # PRIVACY
        # --------------------------------------------------

        try:
            self.can_use_private_memory = (
                privacy_service.is_private_context(
                    group_id=self.group_id
                )
            )
        except Exception:
            logger.exception(
                "Could not check private memory permission."
            )

            self.can_use_private_memory = (
                self.is_private
            )

        self.can_use_group_memory = (
            self.group_id is not None
        )

        # --------------------------------------------------
        # PRIVACY CONTEXT
        # --------------------------------------------------

        if self.is_private:
            self.privacy_context = (
                "PRIVATE CONTEXT\n"
                "==============\n"
                "Bu private chat.\n"
                "Foydalanuvchining private conversation "
                "memorysi ishlatilishi mumkin."
            )

        else:
            self.privacy_context = (
                "GROUP CONTEXT\n"
                "=============\n"
                "Bu group/supergroup context.\n"
                "Private user secrets, passwordlar, "
                "API keylar, tokenlar va boshqa maxfiy "
                "ma'lumotlar guruhga oshkor qilinmaydi."
            )

        # --------------------------------------------------
        # AGENT CONTEXT
        # --------------------------------------------------

        try:
            self.agent_context = (
                await agent_context_builder.build(
                    chat_id=self.chat_id,
                    user_id=self.user_id,
                )
            )

        except Exception:
            logger.exception(
                "Could not build agent context."
            )

            self.agent_context = (
                "SARA AGENT CONTEXT\n"
                "==================\n"
                "Hozircha qo'shimcha context mavjud emas."
            )

        self.prepared = True

        logger.debug(
            "Runtime prepared | "
            "chat=%s user=%s group=%s "
            "private=%s bot=%s",
            self.chat_id,
            self.user_id,
            self.group_id,
            self.is_private,
            self.is_bot_message,
        )

        return self

    # ------------------------------------------------------
    # BUILD CONTEXT
    # ------------------------------------------------------

    def build_agent_context(self) -> dict[str, Any]:
        """
        AI Engine / Orchestrator uchun context.
        """

        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "group_id": self.group_id,

            "is_group": self.is_group,
            "is_private": self.is_private,

            "is_bot": self.is_bot,
            "is_bot_message": self.is_bot_message,

            "sara_called": self.sara_called,
            "is_question": self.is_question,
            "is_reply_to_sara": self.is_reply_to_sara,

            "proactive_allowed": self.proactive_allowed,

            "agent_context": self.agent_context,
            "privacy_context": self.privacy_context,

            "can_use_private_memory": (
                self.can_use_private_memory
            ),

            "can_use_group_memory": (
                self.can_use_group_memory
            ),

            "extra_flags": dict(
                self.extra_flags
            ),
        }

    # ------------------------------------------------------
    # CAN RESPOND
    # ------------------------------------------------------

    def can_respond(self) -> bool:
        """
        SARA hozir javob berishi mumkinligini tekshiradi.
        """

        if self.is_bot_message:
            return False

        if not self.proactive_allowed:
            return False

        try:
            return bool(
                loop_guard.can_respond(
                    chat_id=self.chat_id
                )
            )

        except Exception:
            logger.exception(
                "Could not check loop guard."
            )

            return True

    # ------------------------------------------------------
    # REGISTER RESPONSE
    # ------------------------------------------------------

    def register_response(
        self,
        *,
        response_text: str = "",
    ) -> None:
        """
        SARA javob berganidan keyin state yangilanadi.
        """

        try:
            loop_guard.register_response(
                chat_id=self.chat_id
            )

        except Exception:
            logger.exception(
                "Could not register agent response."
            )

        try:
            loop_guard.register_bot_message(
                chat_id=self.chat_id
            )

        except Exception:
            logger.exception(
                "Could not register bot message."
            )

        try:
            proactive_agent.record_response(
                chat_id=self.chat_id
            )

        except Exception:
            logger.exception(
                "Could not record proactive response."
            )

    # ------------------------------------------------------
    # FINALIZE
    # ------------------------------------------------------

    async def finalize(
        self,
        *,
        response_text: str = "",
        sent: bool = False,
    ) -> None:
        """
        Agent processing yakunlanadi.
        """

        if self.finalized:
            return

        if sent or response_text.strip():
            self.register_response(
                response_text=response_text
            )

        self.finalized = True

        logger.debug(
            "Runtime finalized | "
            "chat=%s user=%s sent=%s",
            self.chat_id,
            self.user_id,
            sent,
        )


class AgentRuntime:
    """
    Legacy compatibility wrapper.

    Eski kodlar AgentRuntime ishlatgan bo'lsa,
    yangi AgentRuntimeContext bilan ishlaydi.
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
        is_bot_message: bool = False,
        proactive_allowed: bool = True,
    ) -> AgentRuntimeContext:

        is_private = (
            group_id is None
            and message.chat.type == "private"
        )

        is_group = (
            group_id is not None
            or message.chat.type in {
                "group",
                "supergroup",
            }
        )

        is_bot = bool(
            message.from_user
            and message.from_user.is_bot
        )

        runtime = AgentRuntimeContext(
            chat_id=int(message.chat.id),
            user_id=int(user_id),
            group_id=group_id,

            is_group=is_group,
            is_private=is_private,

            is_bot=is_bot,
            is_bot_message=is_bot_message,

            sara_called=sara_called,
            is_question=is_question,
            is_reply_to_sara=is_reply_to_sara,

            proactive_allowed=proactive_allowed,
        )

        text = (
            message.text
            or message.caption
            or ""
        )

        await runtime.prepare(
            user_text=text,
            extra_flags={
                "source": "legacy_agent_runtime",
                "is_question": is_question,
                "sara_called": sara_called,
                "is_reply_to_sara": is_reply_to_sara,
                "is_bot_message": is_bot_message,
                "proactive_allowed": proactive_allowed,
            },
        )

        return runtime

    def reset(
        self,
        chat_id: int,
    ) -> None:

        try:
            loop_guard.reset(
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                "Could not reset loop guard."
            )

        try:
            proactive_agent.reset(
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                "Could not reset proactive state."
            )

        try:
            emotional_state.reset(
                chat_id=chat_id
            )
        except Exception:
            logger.exception(
                "Could not reset emotional state."
            )


agent_runtime = AgentRuntime()


__all__ = [
    "AgentRuntimeContext",
    "AgentRuntime",
    "agent_runtime",
            ]
