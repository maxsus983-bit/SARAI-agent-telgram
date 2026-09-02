from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.agent.runtime import AgentRuntimeContext
from app.config.settings import settings

logger = logging.getLogger("sara.agent.brain")


# ============================================================
# ACTION TYPES
# ============================================================


class ActionType(str, Enum):

    IGNORE = "ignore"

    RESPOND = "respond"

    ASK_CLARIFICATION = "ask_clarification"

    REMEMBER = "remember"

    REMINDER = "reminder"

    USE_TOOL = "use_tool"

    CONTINUE_CONVERSATION = "continue_conversation"

    PROACTIVE_MESSAGE = "proactive_message"


# ============================================================
# PRIORITY
# ============================================================


class Priority(str, Enum):

    VERY_LOW = "very_low"

    LOW = "low"

    NORMAL = "normal"

    HIGH = "high"

    CRITICAL = "critical"


# ============================================================
# BRAIN DECISION
# ============================================================


@dataclass
class BrainDecision:

    action: ActionType

    priority: Priority

    confidence: float

    reason: str

    should_respond: bool

    use_memory: bool

    use_group_memory: bool

    use_relationship: bool

    use_emotional_state: bool

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# BRAIN INPUT
# ============================================================


@dataclass
class BrainInput:

    context: AgentRuntimeContext

    user_text: str

    is_command: bool = False

    contains_media: bool = False

    contains_reminder_request: bool = False

    contains_memory_request: bool = False

    contains_tool_request: bool = False


# ============================================================
# SARA BRAIN
# ============================================================


class SaraBrain:

    def __init__(self) -> None:

        self.started_at = time.monotonic()

        self.total_decisions = 0

        self.total_responses = 0

        self.total_ignored = 0

    # ========================================================
    # TEXT ANALYSIS
    # ========================================================

    def _contains_any(
        self,
        text: str,
        words: tuple[str, ...],
    ) -> bool:

        lowered = text.lower()

        return any(
            word in lowered
            for word in words
        )

    # ========================================================
    # REMINDER DETECTION
    # ========================================================

    def _looks_like_reminder(
        self,
        text: str,
    ) -> bool:

        return self._contains_any(
            text,
            (
                "eslat",
                "eslatma",
                "remind",
                "reminder",
                "напомни",
                "напоминание",
            ),
        )

    # ========================================================
    # MEMORY DETECTION
    # ========================================================

    def _looks_like_memory_request(
        self,
        text: str,
    ) -> bool:

        return self._contains_any(
            text,
            (
                "eslab qol",
                "eslab qolgin",
                "yodda saqla",
                "unutma",
                "remember",
                "save this",
                "запомни",
            ),
        )

    # ========================================================
    # TOOL DETECTION
    # ========================================================

    def _looks_like_tool_request(
        self,
        text: str,
    ) -> bool:

        return self._contains_any(
            text,
            (
                "qidir",
                "topib ber",
                "hisobla",
                "tekshir",
                "yubor",
                "yarat",
                "qil",
                "search",
                "find",
                "calculate",
                "check",
                "create",
                "do it",
                "сделай",
                "найди",
                "проверь",
            ),
        )

    # ========================================================
    # PRIORITY
    # ========================================================

    def _calculate_priority(
        self,
        data: BrainInput,
    ) -> Priority:

        context = data.context

        if data.contains_reminder_request:
            return Priority.HIGH

        if data.contains_tool_request:
            return Priority.HIGH

        if context.is_reply_to_sara:
            return Priority.HIGH

        if context.sara_called:
            return Priority.HIGH

        if data.contains_memory_request:
            return Priority.NORMAL

        if context.is_question:
            return Priority.NORMAL

        if context.is_bot:
            return Priority.LOW

        return Priority.LOW

    # ========================================================
    # MEMORY POLICY
    # ========================================================

    def _memory_policy(
        self,
        data: BrainInput,
    ) -> tuple[bool, bool]:

        context = data.context

        # Private chat
        if context.is_private:

            return (
                context.can_use_private_memory,
                False,
            )

        # Group
        #
        # PRIVATE USER MEMORY BU YERDA ISHLATILMAYDI.
        #
        return (
            False,
            context.can_use_group_memory,
        )

    # ========================================================
    # RELATIONSHIP POLICY
    # ========================================================

    def _relationship_policy(
        self,
        data: BrainInput,
    ) -> bool:

        # Relationship faqat real user bilan
        # ishlatiladi.

        if data.context.is_bot:
            return False

        return True

    # ========================================================
    # EMOTIONAL STATE POLICY
    # ========================================================

    def _emotional_policy(
        self,
        data: BrainInput,
    ) -> bool:

        # Session emotional state
        # javob uslubini moslashtirish uchun ishlatiladi.

        return True

    # ========================================================
    # ACTION
    # ========================================================

    def _select_action(
        self,
        data: BrainInput,
    ) -> ActionType:

        context = data.context

        # ----------------------------------------------------
        # COMMAND
        # ----------------------------------------------------

        if data.is_command:
            return ActionType.RESPOND

        # ----------------------------------------------------
        # REMINDER
        # ----------------------------------------------------

        if data.contains_reminder_request:

            return ActionType.REMINDER

        # ----------------------------------------------------
        # MEMORY
        # ----------------------------------------------------

        if data.contains_memory_request:

            return ActionType.REMEMBER

        # ----------------------------------------------------
        # TOOL
        # ----------------------------------------------------

        if data.contains_tool_request:

            return ActionType.USE_TOOL

        # ----------------------------------------------------
        # DIRECT CALL
        # ----------------------------------------------------

        if context.sara_called:

            return ActionType.RESPOND

        # ----------------------------------------------------
        # REPLY
        # ----------------------------------------------------

        if context.is_reply_to_sara:

            return ActionType.RESPOND

        # ----------------------------------------------------
        # QUESTION
        # ----------------------------------------------------

        if context.is_question:

            return ActionType.RESPOND

        # ----------------------------------------------------
        # PRIVATE
        # ----------------------------------------------------

        if context.is_private:

            return ActionType.CONTINUE_CONVERSATION

        # ----------------------------------------------------
        # GROUP
        # ----------------------------------------------------

        return ActionType.IGNORE

    # ========================================================
    # CONFIDENCE
    # ========================================================

    def _calculate_confidence(
        self,
        data: BrainInput,
        action: ActionType,
    ) -> float:

        context = data.context

        score = 0.50

        if context.sara_called:
            score += 0.30

        if context.is_reply_to_sara:
            score += 0.25

        if context.is_question:
            score += 0.10

        if data.contains_reminder_request:
            score += 0.15

        if data.contains_memory_request:
            score += 0.10

        if data.contains_tool_request:
            score += 0.10

        if context.is_bot:
            score -= 0.15

        if action == ActionType.IGNORE:
            score = min(
                score,
                0.60,
            )

        return max(
            0.0,
            min(
                1.0,
                score,
            ),
        )

    # ========================================================
    # MAIN THINK
    # ========================================================

    def think(
        self,
        *,
        context: AgentRuntimeContext,
        user_text: str,
        is_command: bool = False,
        contains_media: bool = False,
    ) -> BrainDecision:

        self.total_decisions += 1

        data = BrainInput(
            context=context,
            user_text=user_text,
            is_command=is_command,
            contains_media=contains_media,
            contains_reminder_request=(
                self._looks_like_reminder(
                    user_text
                )
            ),
            contains_memory_request=(
                self._looks_like_memory_request(
                    user_text
                )
            ),
            contains_tool_request=(
                self._looks_like_tool_request(
                    user_text
                )
            ),
        )

        # ====================================================
        # ACTION
        # ====================================================

        action = self._select_action(
            data
        )

        # ====================================================
        # PRIORITY
        # ====================================================

        priority = self._calculate_priority(
            data
        )

        # ====================================================
        # MEMORY
        # ====================================================

        (
            use_memory,
            use_group_memory,
        ) = self._memory_policy(
            data
        )

        # ====================================================
        # RELATIONSHIP
        # ====================================================

        use_relationship = (
            self._relationship_policy(
                data
            )
        )

        # ====================================================
        # EMOTIONAL
        # ====================================================

        use_emotional_state = (
            self._emotional_policy(
                data
            )
        )

        # ====================================================
        # CONFIDENCE
        # ====================================================

        confidence = (
            self._calculate_confidence(
                data,
                action,
            )
        )

        # ====================================================
        # SHOULD RESPOND
        # ====================================================

        should_respond = (
            action
            not in {
                ActionType.IGNORE,
            }
        )

        # ====================================================
        # BOT SAFETY
        # ====================================================

        if context.is_bot:

            if not settings.bot_to_bot_mode:

                should_respond = False

                action = ActionType.IGNORE

        # ====================================================
        # GROUP SAFETY
        # ====================================================

        if context.is_group:

            if (
                not context.sara_called
                and not context.is_reply_to_sara
                and not context.is_question
                and action
                not in {
                    ActionType.PROACTIVE_MESSAGE,
                }
            ):

                # Guruhda oddiy suhbatga
                # keraksiz aralashmaydi.

                should_respond = False

                action = ActionType.IGNORE

        # ====================================================
        # COUNTERS
        # ====================================================

        if should_respond:

            self.total_responses += 1

        else:

            self.total_ignored += 1

        # ====================================================
        # REASON
        # ====================================================

        reason = self._build_reason(
            data=data,
            action=action,
            priority=priority,
        )

        # ====================================================
        # METADATA
        # ====================================================

        metadata: dict[str, Any] = {

            "chat_id": context.chat_id,

            "user_id": context.user_id,

            "group_id": context.group_id,

            "private": context.is_private,

            "group": context.is_group,

            "bot": context.is_bot,

            "sara_called": context.sara_called,

            "question": context.is_question,

            "reply_to_sara": (
                context.is_reply_to_sara
            ),

            "media": contains_media,

            "memory_allowed": use_memory,

            "group_memory_allowed": (
                use_group_memory
            ),

            "relationship_enabled": (
                use_relationship
            ),

            "emotional_state_enabled": (
                use_emotional_state
            ),
        }

        decision = BrainDecision(
            action=action,
            priority=priority,
            confidence=confidence,
            reason=reason,
            should_respond=should_respond,
            use_memory=use_memory,
            use_group_memory=use_group_memory,
            use_relationship=use_relationship,
            use_emotional_state=use_emotional_state,
            metadata=metadata,
        )

        logger.debug(
            "SARA Brain decision | "
            "chat=%s | action=%s | priority=%s | "
            "confidence=%.2f | reason=%s",
            context.chat_id,
            action.value,
            priority.value,
            confidence,
            reason,
        )

        return decision

    # ========================================================
    # REASON GENERATOR
    # ========================================================

    def _build_reason(
        self,
        *,
        data: BrainInput,
        action: ActionType,
        priority: Priority,
    ) -> str:

        context = data.context

        if data.contains_reminder_request:
            return "reminder_request"

        if data.contains_memory_request:
            return "memory_request"

        if data.contains_tool_request:
            return "tool_request"

        if context.sara_called:
            return "direct_sara_call"

        if context.is_reply_to_sara:
            return "reply_to_sara"

        if context.is_question:
            return "question"

        if context.is_private:
            return "private_conversation"

        if context.is_bot:
            return "bot_message"

        return "no_relevant_trigger"

    # ========================================================
    # STATS
    # ========================================================

    def stats(self) -> dict[str, Any]:

        uptime = (
            time.monotonic()
            - self.started_at
        )

        return {

            "uptime_seconds": round(
                uptime,
                2,
            ),

            "total_decisions": (
                self.total_decisions
            ),

            "total_responses": (
                self.total_responses
            ),

            "total_ignored": (
                self.total_ignored
            ),
        }

    # ========================================================
    # RESET STATS
    # ========================================================

    def reset_stats(self) -> None:

        self.started_at = time.monotonic()

        self.total_decisions = 0

        self.total_responses = 0

        self.total_ignored = 0


# ============================================================
# GLOBAL BRAIN
# ============================================================

sara_brain = SaraBrain()
