from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.agent.brain import (
    ActionType,
    BrainDecision,
)


logger = logging.getLogger("sara.agent.planner")


# ==============================================================
# STEP TYPES
# ==============================================================


class PlanStepType(str, Enum):
    """
    SARA Planner bajarishi mumkin bo'lgan step turlari.
    """

    ANALYZE = "analyze"

    RETRIEVE_MEMORY = "retrieve_memory"
    RETRIEVE_GROUP_MEMORY = "retrieve_group_memory"

    CHECK_RELATIONSHIP = "check_relationship"
    CHECK_SESSION_STATE = "check_session_state"

    GENERATE_RESPONSE = "generate_response"
    ASK_CLARIFICATION = "ask_clarification"

    SAVE_MEMORY = "save_memory"

    CREATE_REMINDER = "create_reminder"

    USE_TOOL = "use_tool"

    SEND_RESPONSE = "send_response"

    FINISH = "finish"


# ==============================================================
# PLAN STEP
# ==============================================================


@dataclass
class PlanStep:
    """
    Bitta execution step.

    Har bir step Executor tomonidan alohida bajariladi.
    """

    id: str

    step_type: PlanStepType

    description: str = ""

    required: bool = True

    arguments: dict[str, Any] = field(
        default_factory=dict
    )

    completed: bool = False

    result: Any = None

    error: str | None = None

    created_at: float = field(
        default_factory=time.time
    )

    completed_at: float | None = None

    # ----------------------------------------------------------
    # COMPLETE
    # ----------------------------------------------------------

    def complete(
        self,
        result: Any = None,
    ) -> None:

        self.completed = True
        self.result = result
        self.error = None
        self.completed_at = time.time()

    # ----------------------------------------------------------
    # FAIL
    # ----------------------------------------------------------

    def fail(
        self,
        error: str,
    ) -> None:

        self.completed = False
        self.error = str(error)

    # ----------------------------------------------------------
    # DICT
    # ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:

        return {
            "id": self.id,
            "step_type": self.step_type.value,
            "description": self.description,
            "required": self.required,
            "arguments": self.arguments,
            "completed": self.completed,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


# ==============================================================
# EXECUTION PLAN
# ==============================================================


@dataclass
class ExecutionPlan:
    """
    SARA agent execution plan.

    Brain qaror beradi.
    Planner shu qarorni step'larga ajratadi.
    Executor step'larni bajaradi.
    """

    plan_id: str

    action: ActionType

    user_text: str

    steps: list[PlanStep] = field(
        default_factory=list
    )

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    current_index: int = 0

    completed: bool = False

    cancelled: bool = False

    cancel_reason: str | None = None

    created_at: float = field(
        default_factory=time.time
    )

    updated_at: float = field(
        default_factory=time.time
    )

    # ----------------------------------------------------------
    # CURRENT STEP
    # ----------------------------------------------------------

    def get_current_step(
        self,
    ) -> PlanStep | None:

        if self.completed or self.cancelled:
            return None

        if (
            self.current_index < 0
            or self.current_index >= len(
                self.steps
            )
        ):
            return None

        return self.steps[
            self.current_index
        ]

    # ----------------------------------------------------------
    # COMPLETE CURRENT STEP
    # ----------------------------------------------------------

    def complete_current_step(
        self,
        result: Any = None,
    ) -> None:

        step = self.get_current_step()

        if step is None:
            return

        step.complete(result)

        self.current_index += 1
        self.updated_at = time.time()

        if self.current_index >= len(
            self.steps
        ):
            self.completed = True

    # ----------------------------------------------------------
    # FAIL CURRENT STEP
    # ----------------------------------------------------------

    def fail_current_step(
        self,
        error: str,
    ) -> None:

        step = self.get_current_step()

        if step is None:
            return

        step.fail(error)

        self.updated_at = time.time()

    # ----------------------------------------------------------
    # CANCEL
    # ----------------------------------------------------------

    def cancel(
        self,
        reason: str,
    ) -> None:

        self.cancelled = True
        self.cancel_reason = str(reason)
        self.updated_at = time.time()

    # ----------------------------------------------------------
    # PROGRESS
    # ----------------------------------------------------------

    @property
    def progress(self) -> float:

        if not self.steps:
            return 1.0

        completed = sum(
            1
            for step in self.steps
            if step.completed
        )

        return completed / len(
            self.steps
        )

    # ----------------------------------------------------------
    # TO DICT
    # ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:

        return {
            "plan_id": self.plan_id,
            "action": self.action.value,
            "user_text": self.user_text,
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
            "metadata": self.metadata,
            "current_index": self.current_index,
            "completed": self.completed,
            "cancelled": self.cancelled,
            "cancel_reason": self.cancel_reason,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ==============================================================
# PLANNER
# ==============================================================


class SaraPlanner:
    """
    SARA AI Planner.

    Vazifasi:

        BrainDecision
              ↓
        ExecutionPlan
              ↓
        Executor
    """

    def __init__(self) -> None:

        self.total_plans = 0
        self.completed_plans = 0
        self.cancelled_plans = 0

    # ==========================================================
    # CREATE PLAN
    # ==========================================================

    async def create_plan(
        self,
        *,
        decision: BrainDecision,
        user_text: str,
        chat_id: int,
        user_id: int | None,
        group_id: int | None = None,
        reply_to_message_id: int | None = None,
        response_text: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionPlan:

        self.total_plans += 1

        plan_id = (
            f"sara-plan-"
            f"{int(time.time())}-"
            f"{uuid.uuid4().hex[:8]}"
        )

        plan_metadata: dict[str, Any] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "group_id": group_id,
            "reply_to_message_id": (
                reply_to_message_id
            ),

            "response_text": (
                response_text or ""
            ),

            "brain_reason": getattr(
                decision,
                "reason",
                "",
            ),

            "brain_confidence": getattr(
                decision,
                "confidence",
                0.0,
            ),

            "brain_priority": str(
                getattr(
                    decision,
                    "priority",
                    "",
                )
            ),

            "brain_action": str(
                decision.action
            ),

            "source_text": user_text,

            **(
                metadata
                if isinstance(
                    metadata,
                    dict,
                )
                else {}
            ),
        }

        plan = ExecutionPlan(
            plan_id=plan_id,
            action=decision.action,
            user_text=user_text,
            metadata=plan_metadata,
        )

        # ======================================================
        # ANALYZE — ALWAYS
        # ======================================================

        self._add_step(
            plan,
            PlanStepType.ANALYZE,
            "Brain qarorini va mavjud contextni analiz qilish.",
            required=True,
            arguments={
                "action": str(
                    decision.action
                ),
                "priority": str(
                    getattr(
                        decision,
                        "priority",
                        "",
                    )
                ),
                "confidence": getattr(
                    decision,
                    "confidence",
                    0.0,
                ),
            },
        )

        # ======================================================
        # USER MEMORY
        # ======================================================

        if (
            getattr(
                decision,
                "use_memory",
                False,
            )
            and user_id is not None
        ):

            self._add_step(
                plan,
                PlanStepType.RETRIEVE_MEMORY,
                "User memory'dan relevant ma'lumotlarni olish.",
                required=False,
                arguments={
                    "user_telegram_id": user_id,
                    "query": user_text,
                },
            )

        # ======================================================
        # GROUP MEMORY
        # ======================================================

        if (
            getattr(
                decision,
                "use_group_memory",
                False,
            )
            and group_id is not None
        ):

            self._add_step(
                plan,
                PlanStepType.RETRIEVE_GROUP_MEMORY,
                "Group memory'dan relevant ma'lumotlarni olish.",
                required=False,
                arguments={
                    "group_telegram_id": group_id,
                    "query": user_text,
                },
            )

        # ======================================================
        # RELATIONSHIP
        # ======================================================

        if getattr(
            decision,
            "use_relationship",
            False,
        ):

            self._add_step(
                plan,
                PlanStepType.CHECK_RELATIONSHIP,
                "User bilan relationship contextni tekshirish.",
                required=False,
                arguments={
                    "user_id": user_id,
                    "chat_id": chat_id,
                },
            )

        # ======================================================
        # EMOTIONAL / SESSION STATE
        # ======================================================

        if getattr(
            decision,
            "use_emotional_state",
            False,
        ):

            self._add_step(
                plan,
                PlanStepType.CHECK_SESSION_STATE,
                "SARA session/emotional state'ni tekshirish.",
                required=False,
                arguments={
                    "user_id": user_id,
                    "chat_id": chat_id,
                },
            )

        # ======================================================
        # ACTION
        # ======================================================

        action = decision.action

        # ------------------------------------------------------
        # IGNORE
        # ------------------------------------------------------

        if action == ActionType.IGNORE:

            # Ignore uchun AI ham, Telegram send ham kerak emas.
            pass

        # ------------------------------------------------------
        # ASK CLARIFICATION
        # ------------------------------------------------------

        elif action == ActionType.ASK_CLARIFICATION:

            self._add_step(
                plan,
                PlanStepType.ASK_CLARIFICATION,
                "Userdan kerakli aniqlikni so'rash.",
                required=True,
                arguments={
                    "user_text": user_text,
                },
            )

            self._add_response_steps(
                plan,
                response_text=response_text,
                required=True,
            )

        # ------------------------------------------------------
        # REMEMBER
        # ------------------------------------------------------

        elif action == ActionType.REMEMBER:

            self._add_step(
                plan,
                PlanStepType.SAVE_MEMORY,
                "Muhim ma'lumotni persistent memory'ga saqlash.",
                required=True,
                arguments={
                    "user_telegram_id": user_id,
                    "group_telegram_id": group_id,
                    "chat_id": chat_id,
                    "text": user_text,
                    "source_message_id": (
                        reply_to_message_id
                    ),
                    "memory_type": "important_fact",
                },
            )

            self._add_response_steps(
                plan,
                response_text=response_text,
                required=False,
            )

        # ------------------------------------------------------
        # REMINDER
        # ------------------------------------------------------

        elif action == ActionType.REMINDER:

            self._add_step(
                plan,
                PlanStepType.CREATE_REMINDER,
                "Reminder yaratish va scheduler'ga qo'shish.",
                required=True,
                arguments={
                    "owner_telegram_id": user_id,
                    "chat_id": chat_id,
                    "text": user_text,
                },
            )

            self._add_response_steps(
                plan,
                response_text=response_text,
                required=True,
            )

        # ------------------------------------------------------
        # USE TOOL
        # ------------------------------------------------------

        elif action == ActionType.USE_TOOL:

            tool_name = self._get_tool_name(
                decision
            )

            tool_arguments = (
                self._get_tool_arguments(
                    decision
                )
            )

            self._add_step(
                plan,
                PlanStepType.USE_TOOL,
                f"Tool ishlatish: {tool_name or 'unknown'}",
                required=True,
                arguments={
                    "tool_name": tool_name,
                    "arguments": tool_arguments,
                },
            )

            self._add_response_steps(
                plan,
                response_text=response_text,
                required=True,
            )

        # ------------------------------------------------------
        # NORMAL RESPONSE
        # ------------------------------------------------------

        elif action in {
            ActionType.RESPOND,
            ActionType.CONTINUE_CONVERSATION,
            ActionType.PROACTIVE_MESSAGE,
        }:

            self._add_response_steps(
                plan,
                response_text=response_text,
                required=True,
            )

        # ------------------------------------------------------
        # FALLBACK
        # ------------------------------------------------------

        else:

            logger.warning(
                "Unknown Brain action: %s",
                action,
            )

            self._add_response_steps(
                plan,
                response_text=response_text,
                required=False,
            )

        # ======================================================
        # FINISH — ALWAYS
        # ======================================================

        self._add_step(
            plan,
            PlanStepType.FINISH,
            "Agent executionni yakunlash.",
            required=True,
        )

        logger.info(
            "Plan created | id=%s | action=%s | steps=%s",
            plan.plan_id,
            plan.action,
            len(plan.steps),
        )

        return plan

    # ==========================================================
    # RESPONSE STEPS
    # ==========================================================

    def _add_response_steps(
        self,
        plan: ExecutionPlan,
        *,
        response_text: str,
        required: bool,
    ) -> None:

        self._add_step(
            plan,
            PlanStepType.GENERATE_RESPONSE,
            "AI response tayyorlash.",
            required=required,
            arguments={
                "response_text": (
                    response_text or ""
                ),
            },
        )

        self._add_step(
            plan,
            PlanStepType.SEND_RESPONSE,
            "Tayyor response'ni Telegramga yuborish.",
            required=required,
            arguments={
                "chat_id": plan.metadata.get(
                    "chat_id"
                ),
                "reply_to_message_id": plan.metadata.get(
                    "reply_to_message_id"
                ),
            },
        )

    # ==========================================================
    # ADD STEP
    # ==========================================================

    @staticmethod
    def _add_step(
        plan: ExecutionPlan,
        step_type: PlanStepType,
        description: str,
        *,
        required: bool = True,
        arguments: dict[str, Any] | None = None,
    ) -> PlanStep:

        step = PlanStep(
            id=uuid.uuid4().hex,
            step_type=step_type,
            description=description,
            required=required,
            arguments=dict(
                arguments or {}
            ),
        )

        plan.steps.append(
            step
        )

        return step

    # ==========================================================
    # TOOL NAME
    # ==========================================================

    @staticmethod
    def _get_tool_name(
        decision: BrainDecision,
    ) -> str:

        metadata = getattr(
            decision,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):
            return ""

        tool_name = metadata.get(
            "tool_name",
            ""
        )

        return str(
            tool_name or ""
        ).strip()

    # ==========================================================
    # TOOL ARGUMENTS
    # ==========================================================

    @staticmethod
    def _get_tool_arguments(
        decision: BrainDecision,
    ) -> dict[str, Any]:

        metadata = getattr(
            decision,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):
            return {}

        arguments = metadata.get(
            "tool_arguments",
            {}
        )

        if not isinstance(
            arguments,
            dict,
        ):
            return {}

        return dict(
            arguments
        )

    # ==========================================================
    # VALIDATE PLAN
    # ==========================================================

    @staticmethod
    def validate_plan(
        plan: ExecutionPlan,
    ) -> tuple[bool, str | None]:

        if not plan.steps:

            return (
                False,
                "Plan bo'sh.",
            )

        if plan.action is None:

            return (
                False,
                "Plan action mavjud emas.",
            )

        for step in plan.steps:

            if not isinstance(
                step.step_type,
                PlanStepType,
            ):

                return (
                    False,
                    f"Noto'g'ri step type: "
                    f"{step.step_type}",
                )

        return (
            True,
            None,
        )

    # ==========================================================
    # MARK COMPLETED
    # ==========================================================

    def mark_plan_completed(
        self,
        plan: ExecutionPlan,
    ) -> None:

        plan.completed = True
        plan.updated_at = time.time()

        self.completed_plans += 1

    # ==========================================================
    # MARK CANCELLED
    # ==========================================================

    def mark_plan_cancelled(
        self,
        plan: ExecutionPlan,
        reason: str,
    ) -> None:

        plan.cancel(
            reason
        )

        self.cancelled_plans += 1

    # ==========================================================
    # STATS
    # ==========================================================

    def stats(self) -> dict[str, int]:

        return {
            "total_plans": self.total_plans,
            "completed_plans": self.completed_plans,
            "cancelled_plans": self.cancelled_plans,
        }

    # ==========================================================
    # RESET STATS
    # ==========================================================

    def reset_stats(self) -> None:

        self.total_plans = 0
        self.completed_plans = 0
        self.cancelled_plans = 0


# ==============================================================
# GLOBAL PLANNER
# ==============================================================

sara_planner = SaraPlanner()


__all__ = [
    "PlanStepType",
    "PlanStep",
    "ExecutionPlan",
    "SaraPlanner",
    "sara_planner",
]
