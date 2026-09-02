from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.agent.brain import (
    ActionType,
    BrainDecision,
    Priority,
)

logger = logging.getLogger("sara.agent.planner")


# ============================================================
# PLAN STEP TYPE
# ============================================================


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


# ============================================================
# PLAN STEP
# ============================================================


@dataclass
class PlanStep:

    id: int

    step_type: PlanStepType

    description: str

    required: bool = True

    completed: bool = False

    result: Any = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# EXECUTION PLAN
# ============================================================


@dataclass
class ExecutionPlan:

    plan_id: str

    action: ActionType

    priority: Priority

    confidence: float

    reason: str

    steps: list[PlanStep] = field(
        default_factory=list
    )

    created_at: float = field(
        default_factory=time.monotonic
    )

    current_step: int = 0

    completed: bool = False

    cancelled: bool = False

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    # ========================================================
    # CURRENT STEP
    # ========================================================

    def get_current_step(
        self,
    ) -> PlanStep | None:

        if self.completed:
            return None

        if self.cancelled:
            return None

        if (
            self.current_step < 0
            or self.current_step >= len(self.steps)
        ):
            return None

        return self.steps[
            self.current_step
        ]

    # ========================================================
    # COMPLETE STEP
    # ========================================================

    def complete_current_step(
        self,
        result: Any = None,
    ) -> PlanStep | None:

        step = self.get_current_step()

        if step is None:
            return None

        step.completed = True
        step.result = result

        self.current_step += 1

        if (
            self.current_step
            >= len(self.steps)
        ):
            self.completed = True

        return step

    # ========================================================
    # FAIL / CANCEL
    # ========================================================

    def cancel(
        self,
        reason: str = "",
    ) -> None:

        self.cancelled = True

        self.metadata[
            "cancel_reason"
        ] = reason

    # ========================================================
    # PROGRESS
    # ========================================================

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


# ============================================================
# SARA PLANNER
# ============================================================


class SaraPlanner:

    def __init__(self) -> None:

        self._counter = 0

        self._active_plans: dict[
            str,
            ExecutionPlan,
        ] = {}

    # ========================================================
    # PLAN ID
    # ========================================================

    def _create_plan_id(
        self,
    ) -> str:

        self._counter += 1

        return (
            f"sara-plan-"
            f"{int(time.time())}-"
            f"{self._counter}"
        )

    # ========================================================
    # STEP
    # ========================================================

    def _step(
        self,
        *,
        number: int,
        step_type: PlanStepType,
        description: str,
        required: bool = True,
        **metadata: Any,
    ) -> PlanStep:

        return PlanStep(
            id=number,
            step_type=step_type,
            description=description,
            required=required,
            metadata=metadata,
        )

    # ========================================================
    # BASE CONTEXT STEPS
    # ========================================================

    def _add_context_steps(
        self,
        *,
        decision: BrainDecision,
        steps: list[PlanStep],
    ) -> int:

        number = len(steps) + 1

        # ----------------------------------------------------
        # MEMORY
        # ----------------------------------------------------

        if decision.use_memory:

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.RETRIEVE_MEMORY
                    ),
                    description=(
                        "Private user memoryni "
                        "tekshirish."
                    ),
                )
            )

            number += 1

        # ----------------------------------------------------
        # GROUP MEMORY
        # ----------------------------------------------------

        if decision.use_group_memory:

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.RETRIEVE_GROUP_MEMORY
                    ),
                    description=(
                        "Guruh memorysini "
                        "tekshirish."
                    ),
                )
            )

            number += 1

        # ----------------------------------------------------
        # RELATIONSHIP
        # ----------------------------------------------------

        if decision.use_relationship:

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.CHECK_RELATIONSHIP
                    ),
                    description=(
                        "SARA va user "
                        "relationship holatini "
                        "tekshirish."
                    ),
                )
            )

            number += 1

        # ----------------------------------------------------
        # EMOTIONAL STATE
        # ----------------------------------------------------

        if decision.use_emotional_state:

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.CHECK_SESSION_STATE
                    ),
                    description=(
                        "Session state va "
                        "javob uslubini "
                        "aniqlash."
                    ),
                )
            )

            number += 1

        return number

    # ========================================================
    # THINK → PLAN
    # ========================================================

    def create_plan(
        self,
        *,
        decision: BrainDecision,
        user_text: str,
    ) -> ExecutionPlan:

        plan_id = self._create_plan_id()

        steps: list[PlanStep] = []

        # ====================================================
        # INITIAL ANALYSIS
        # ====================================================

        steps.append(
            self._step(
                number=1,
                step_type=PlanStepType.ANALYZE,
                description=(
                    "Foydalanuvchi xabarini "
                    "va Brain qarorini "
                    "tahlil qilish."
                ),
            )
        )

        # ====================================================
        # CONTEXT
        # ====================================================

        self._add_context_steps(
            decision=decision,
            steps=steps,
        )

        # ====================================================
        # ACTION
        # ====================================================

        number = len(steps) + 1

        if (
            decision.action
            == ActionType.RESPOND
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.GENERATE_RESPONSE
                    ),
                    description=(
                        "AI yordamida tabiiy "
                        "javob yaratish."
                    ),
                )
            )

            number += 1

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.SEND_RESPONSE
                    ),
                    description=(
                        "Yaratilgan javobni "
                        "Telegramga yuborish."
                    ),
                )
            )

            number += 1

        elif (
            decision.action
            == ActionType.ASK_CLARIFICATION
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.ASK_CLARIFICATION
                    ),
                    description=(
                        "Yetishmayotgan "
                        "ma'lumotni userdan "
                        "so'rash."
                    ),
                )
            )

            number += 1

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.SEND_RESPONSE
                    ),
                    description=(
                        "Aniqlashtiruvchi "
                        "savolni yuborish."
                    ),
                )
            )

            number += 1

        elif (
            decision.action
            == ActionType.REMEMBER
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.SAVE_MEMORY
                    ),
                    description=(
                        "Foydalanuvchi so'roviga "
                        "ko'ra memoryni "
                        "saqlash."
                    ),
                )
            )

            number += 1

        elif (
            decision.action
            == ActionType.REMINDER
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.CREATE_REMINDER
                    ),
                    description=(
                        "Reminder ma'lumotlarini "
                        "aniqlash va yaratish."
                    ),
                )

            number += 1

        elif (
            decision.action
            == ActionType.USE_TOOL
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.USE_TOOL
                    ),
                    description=(
                        "Kerakli toolni "
                        "aniqlash va "
                        "ishlatish."
                    ),
                )
            )

            number += 1

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.GENERATE_RESPONSE
                    ),
                    description=(
                        "Tool natijasiga "
                        "asoslangan javob "
                        "yaratish."
                    ),
                )
            )

            number += 1

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.SEND_RESPONSE
                    ),
                    description=(
                        "Natijani userga "
                        "yuborish."
                    ),
                )
            )

            number += 1

        elif (
            decision.action
            == ActionType.CONTINUE_CONVERSATION
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.GENERATE_RESPONSE
                    ),
                    description=(
                        "Private suhbatni "
                        "tabiiy davom ettirish."
                    ),
                )
            )

            number += 1

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.SEND_RESPONSE
                    ),
                    description=(
                        "Javobni userga "
                        "yuborish."
                    ),
                )
            )

            number += 1

        elif (
            decision.action
            == ActionType.PROACTIVE_MESSAGE
        ):

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.GENERATE_RESPONSE
                    ),
                    description=(
                        "Guruh kontekstiga "
                        "mos proactive "
                        "xabar yaratish."
                    ),
                )
            )

            number += 1

            steps.append(
                self._step(
                    number=number,
                    step_type=(
                        PlanStepType.SEND_RESPONSE
                    ),
                    description=(
                        "Proactive xabarni "
                        "guruhga yuborish."
                    ),
                )

            number += 1

        # ====================================================
        # FINISH
        # ====================================================

        steps.append(
            self._step(
                number=number,
                step_type=PlanStepType.FINISH,
                description=(
                    "Agent ishini "
                    "yakunlash."
                ),
            )
        )

        # ====================================================
        # PLAN
        # ====================================================

        plan = ExecutionPlan(
            plan_id=plan_id,
            action=decision.action,
            priority=decision.priority,
            confidence=decision.confidence,
            reason=decision.reason,
            steps=steps,
            metadata={
                "user_text_length": len(
                    user_text
                ),
                "created_by": "sara_brain",
            },
        )

        self._active_plans[
            plan_id
        ] = plan

        logger.info(
            "Plan created | id=%s | action=%s | "
            "priority=%s | steps=%s",
            plan.plan_id,
            plan.action.value,
            plan.priority.value,
            len(plan.steps),
        )

        return plan

    # ========================================================
    # ACTIVE PLAN
    # ========================================================

    def get_plan(
        self,
        plan_id: str,
    ) -> ExecutionPlan | None:

        return self._active_plans.get(
            plan_id
        )

    # ========================================================
    # COMPLETE STEP
    # ========================================================

    def complete_step(
        self,
        *,
        plan_id: str,
        result: Any = None,
    ) -> PlanStep | None:

        plan = self.get_plan(
            plan_id
        )

        if plan is None:
            return None

        step = plan.complete_current_step(
            result
        )

        if plan.completed:

            logger.info(
                "Plan completed | id=%s",
                plan_id,
            )

        return step

    # ========================================================
    # CANCEL PLAN
    # ========================================================

    def cancel_plan(
        self,
        *,
        plan_id: str,
        reason: str = "",
    ) -> bool:

        plan = self.get_plan(
            plan_id
        )

        if plan is None:
            return False

        plan.cancel(
            reason=reason
        )

        logger.warning(
            "Plan cancelled | id=%s | reason=%s",
            plan_id,
            reason,
        )

        return True

    # ========================================================
    # REMOVE FINISHED
    # ========================================================

    def cleanup(
        self,
        *,
        max_age_seconds: int = 3600,
    ) -> int:

        now = time.monotonic()

        expired: list[str] = []

        for plan_id, plan in (
            self._active_plans.items()
        ):

            if not (
                plan.completed
                or plan.cancelled
            ):
                continue

            if (
                now - plan.created_at
                > max_age_seconds
            ):

                expired.append(
                    plan_id
                )

        for plan_id in expired:

            self._active_plans.pop(
                plan_id,
                None,
            )

        return len(expired)

    # ========================================================
    # STATS
    # ========================================================

    def stats(self) -> dict[str, int]:

        active = 0
        completed = 0
        cancelled = 0

        for plan in self._active_plans.values():

            if plan.cancelled:

                cancelled += 1

            elif plan.completed:

                completed += 1

            else:

                active += 1

        return {
            "total": len(
                self._active_plans
            ),
            "active": active,
            "completed": completed,
            "cancelled": cancelled,
        }


# ============================================================
# GLOBAL PLANNER
# ============================================================

sara_planner = SaraPlanner()
