from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.agent.brain import ActionType, BrainDecision

logger = logging.getLogger("sara.agent.planner")


class PlanStepType(str, Enum):
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


@dataclass
class PlanStep:
    id: int
    step_type: PlanStepType
    description: str
    required: bool = True
    arguments: dict[str, Any] = field(default_factory=dict)
    completed: bool = False
    result: Any = None


@dataclass
class ExecutionPlan:
    plan_id: str
    action: ActionType
    user_text: str

    steps: list[PlanStep] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    current_index: int = 0
    completed: bool = False
    cancelled: bool = False
    cancel_reason: str | None = None

    created_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)

    def get_current_step(self) -> PlanStep | None:
        if self.completed or self.cancelled:
            return None

        if self.current_index >= len(self.steps):
            return None

        return self.steps[self.current_index]

    def complete_current_step(
        self,
        result: Any = None,
    ) -> None:
        step = self.get_current_step()

        if step is None:
            return

        step.completed = True
        step.result = result

        self.current_index += 1
        self.updated_at = time.monotonic()

        if self.current_index >= len(self.steps):
            self.completed = True

    def cancel(
        self,
        reason: str,
    ) -> None:
        self.cancelled = True
        self.cancel_reason = reason
        self.updated_at = time.monotonic()

    @property
    def progress(self) -> float:
        if not self.steps:
            return 1.0

        completed = sum(
            1
            for step in self.steps
            if step.completed
        )

        return completed / len(self.steps)


class SaraPlanner:

    def __init__(self) -> None:
        self._plans: dict[str, ExecutionPlan] = {}

    # =========================================================
    # CREATE PLAN
    # =========================================================

    def create_plan(
        self,
        *,
        decision: BrainDecision,
        user_text: str,
        chat_id: int | None = None,
        user_id: int | None = None,
        group_id: int | None = None,
        reply_to_message_id: int | None = None,
        response_text: str | None = None,
    ) -> ExecutionPlan:

        plan_id = uuid.uuid4().hex

        metadata: dict[str, Any] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "group_id": group_id,
            "reply_to_message_id": reply_to_message_id,
            "response_text": response_text,
            "brain_reason": decision.reason,
            "brain_confidence": decision.confidence,
        }

        steps: list[PlanStep] = []

        # -----------------------------------------------------
        # ALWAYS ANALYZE
        # -----------------------------------------------------

        steps.append(
            PlanStep(
                id=1,
                step_type=PlanStepType.ANALYZE,
                description="Foydalanuvchi xabarini tahlil qilish.",
            )
        )

        step_id = 2

        # -----------------------------------------------------
        # MEMORY
        # -----------------------------------------------------

        if decision.use_memory:
            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.RETRIEVE_MEMORY,
                    description="User memory ma'lumotlarini olish.",
                    required=False,
                )
            )
            step_id += 1

        if decision.use_group_memory and group_id is not None:
            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.RETRIEVE_GROUP_MEMORY,
                    description="Group memory ma'lumotlarini olish.",
                    required=False,
                )
            )
            step_id += 1

        # -----------------------------------------------------
        # RELATIONSHIP
        # -----------------------------------------------------

        if decision.use_relationship:
            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.CHECK_RELATIONSHIP,
                    description="SARA va foydalanuvchi relationship holatini tekshirish.",
                    required=False,
                )
            )
            step_id += 1

        # -----------------------------------------------------
        # EMOTIONAL SESSION
        # -----------------------------------------------------

        if decision.use_emotional_state:
            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.CHECK_SESSION_STATE,
                    description="SARA session state holatini tekshirish.",
                    required=False,
                )
            )
            step_id += 1

        # -----------------------------------------------------
        # ACTION
        # -----------------------------------------------------

        if decision.action == ActionType.ASK_CLARIFICATION:

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.ASK_CLARIFICATION,
                    description="Aniqlashtiruvchi javob tayyorlash.",
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.SEND_RESPONSE,
                    description="Aniqlashtiruvchi xabarni Telegramga yuborish.",
                    arguments={
                        "chat_id": chat_id,
                        "text": response_text,
                        "reply_to_message_id": reply_to_message_id,
                    },
                )
            )

            step_id += 1

        elif decision.action == ActionType.REMEMBER:

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.SAVE_MEMORY,
                    description="Muhim ma'lumotni memory tizimiga saqlash.",
                    arguments={
                        "user_id": user_id,
                        "group_id": group_id,
                        "text": user_text,
                    },
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.GENERATE_RESPONSE,
                    description="Memory saqlangani haqida javob tayyorlash.",
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.SEND_RESPONSE,
                    description="Javobni Telegramga yuborish.",
                    arguments={
                        "chat_id": chat_id,
                        "text": response_text,
                        "reply_to_message_id": reply_to_message_id,
                    },
                )
            )

            step_id += 1

        elif decision.action == ActionType.REMINDER:

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.CREATE_REMINDER,
                    description="Reminder yaratish.",
                    arguments={
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "text": user_text,
                    },
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.GENERATE_RESPONSE,
                    description="Reminder yaratilgani haqida javob tayyorlash.",
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.SEND_RESPONSE,
                    description="Reminder javobini Telegramga yuborish.",
                    arguments={
                        "chat_id": chat_id,
                        "text": response_text,
                        "reply_to_message_id": reply_to_message_id,
                    },
                )
            )

            step_id += 1

        elif decision.action == ActionType.USE_TOOL:

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.USE_TOOL,
                    description="Tanlangan SARA toolini ishga tushirish.",
                    arguments={
                        "tool_name": decision.metadata.get("tool_name"),
                        "tool_arguments": decision.metadata.get(
                            "tool_arguments",
                            {},
                        ),
                    },
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.GENERATE_RESPONSE,
                    description="Tool natijasidan javob tayyorlash.",
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.SEND_RESPONSE,
                    description="Tool natijasini Telegramga yuborish.",
                    arguments={
                        "chat_id": chat_id,
                        "text": response_text,
                        "reply_to_message_id": reply_to_message_id,
                    },
                )
            )

            step_id += 1

        elif decision.action in {
            ActionType.RESPOND,
            ActionType.CONTINUE_CONVERSATION,
            ActionType.PROACTIVE_MESSAGE,
        }:

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.GENERATE_RESPONSE,
                    description="AI javobini tayyorlash.",
                    arguments={
                        "response_text": response_text,
                    },
                )
            )

            step_id += 1

            steps.append(
                PlanStep(
                    id=step_id,
                    step_type=PlanStepType.SEND_RESPONSE,
                    description="AI javobini Telegramga yuborish.",
                    arguments={
                        "chat_id": chat_id,
                        "text": response_text,
                        "reply_to_message_id": reply_to_message_id,
                    },
                )
            )

            step_id += 1

        # -----------------------------------------------------
        # FINISH
        # -----------------------------------------------------

        steps.append(
            PlanStep(
                id=step_id,
                step_type=PlanStepType.FINISH,
                description="Agent actionni yakunlash.",
            )
        )

        plan = ExecutionPlan(
            plan_id=plan_id,
            action=decision.action,
            user_text=user_text,
            steps=steps,
            metadata=metadata,
        )

        self._plans[plan_id] = plan

        logger.info(
            "Plan created | id=%s | action=%s | steps=%s",
            plan_id,
            decision.action.value,
            len(steps),
        )

        return plan

    # =========================================================
    # PLAN MANAGEMENT
    # =========================================================

    def get_plan(
        self,
        plan_id: str,
    ) -> ExecutionPlan | None:
        return self._plans.get(plan_id)

    def complete_step(
        self,
        plan_id: str,
        result: Any = None,
    ) -> bool:

        plan = self.get_plan(plan_id)

        if plan is None:
            return False

        plan.complete_current_step(result)

        return True

    def cancel_plan(
        self,
        plan_id: str,
        reason: str,
    ) -> bool:

        plan = self.get_plan(plan_id)

        if plan is None:
            return False

        plan.cancel(reason)

        return True

    def cleanup(
        self,
        *,
        max_age_seconds: int = 3600,
    ) -> int:

        now = time.monotonic()

        expired: list[str] = []

        for plan_id, plan in self._plans.items():

            if now - plan.updated_at > max_age_seconds:
                expired.append(plan_id)

        for plan_id in expired:
            self._plans.pop(plan_id, None)

        return len(expired)

    def stats(self) -> dict[str, int]:

        return {
            "active_plans": len(self._plans),
            "completed_plans": sum(
                1
                for plan in self._plans.values()
                if plan.completed
            ),
            "cancelled_plans": sum(
                1
                for plan in self._plans.values()
                if plan.cancelled
            ),
        }


sara_planner = SaraPlanner()
