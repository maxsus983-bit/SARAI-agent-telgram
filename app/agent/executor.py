from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.agent.brain import ActionType
from app.agent.planner import (
    ExecutionPlan,
    PlanStep,
    PlanStepType,
)

logger = logging.getLogger("sara.agent.executor")


# ============================================================
# TYPES
# ============================================================

StepHandler = Callable[
    [ExecutionPlan, PlanStep],
    Awaitable[Any],
]


# ============================================================
# EXECUTION RESULT
# ============================================================

@dataclass
class ExecutionResult:

    success: bool

    plan_id: str

    action: ActionType

    completed_steps: int

    total_steps: int

    result: Any = None

    error: str | None = None

    duration_seconds: float = 0.0


# ============================================================
# EXECUTOR
# ============================================================

class SaraExecutor:

    def __init__(self) -> None:

        self._handlers: dict[
            PlanStepType,
            StepHandler,
        ] = {}

        self.total_executions = 0

        self.successful_executions = 0

        self.failed_executions = 0

        self.total_steps = 0

        self.successful_steps = 0

        self.failed_steps = 0

        self._register_default_handlers()

    # ========================================================
    # HANDLERS
    # ========================================================

    def _register_default_handlers(
        self,
    ) -> None:

        self.register_handler(
            PlanStepType.ANALYZE,
            self._handle_analyze,
        )

        self.register_handler(
            PlanStepType.RETRIEVE_MEMORY,
            self._handle_retrieve_memory,
        )

        self.register_handler(
            PlanStepType.RETRIEVE_GROUP_MEMORY,
            self._handle_retrieve_group_memory,
        )

        self.register_handler(
            PlanStepType.CHECK_RELATIONSHIP,
            self._handle_relationship,
        )

        self.register_handler(
            PlanStepType.CHECK_SESSION_STATE,
            self._handle_session_state,
        )

        self.register_handler(
            PlanStepType.GENERATE_RESPONSE,
            self._handle_generate_response,
        )

        self.register_handler(
            PlanStepType.ASK_CLARIFICATION,
            self._handle_clarification,
        )

        self.register_handler(
            PlanStepType.SAVE_MEMORY,
            self._handle_save_memory,
        )

        self.register_handler(
            PlanStepType.CREATE_REMINDER,
            self._handle_create_reminder,
        )

        self.register_handler(
            PlanStepType.USE_TOOL,
            self._handle_use_tool,
        )

        self.register_handler(
            PlanStepType.SEND_RESPONSE,
            self._handle_send_response,
        )

        self.register_handler(
            PlanStepType.FINISH,
            self._handle_finish,
        )

    # ========================================================
    # REGISTER HANDLER
    # ========================================================

    def register_handler(
        self,
        step_type: PlanStepType,
        handler: StepHandler,
    ) -> None:

        self._handlers[
            step_type
        ] = handler

        logger.debug(
            "Executor handler registered | step=%s",
            step_type.value,
        )

    # ========================================================
    # CHECK HANDLER
    # ========================================================

    def has_handler(
        self,
        step_type: PlanStepType,
    ) -> bool:

        return (
            step_type
            in self._handlers
        )

    # ========================================================
    # EXECUTE PLAN
    # ========================================================

    async def execute(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:

        started = time.monotonic()

        self.total_executions += 1

        logger.info(
            "Executing plan | id=%s | action=%s",
            plan.plan_id,
            plan.action.value,
        )

        if plan.cancelled:

            return ExecutionResult(
                success=False,
                plan_id=plan.plan_id,
                action=plan.action,
                completed_steps=0,
                total_steps=len(plan.steps),
                error="plan_cancelled",
                duration_seconds=(
                    time.monotonic()
                    - started
                ),
            )

        if plan.completed:

            return ExecutionResult(
                success=True,
                plan_id=plan.plan_id,
                action=plan.action,
                completed_steps=len(
                    plan.steps
                ),
                total_steps=len(
                    plan.steps
                ),
                result="already_completed",
                duration_seconds=(
                    time.monotonic()
                    - started
                ),
            )

        last_result: Any = None

        try:

            while not plan.completed:

                if plan.cancelled:

                    raise RuntimeError(
                        "Plan cancelled during execution."
                    )

                step = plan.get_current_step()

                if step is None:

                    break

                self.total_steps += 1

                handler = self._handlers.get(
                    step.step_type
                )

                if handler is None:

                    self.failed_steps += 1

                    raise RuntimeError(
                        "No executor handler for "
                        f"{step.step_type.value}"
                    )

                logger.debug(
                    "Executing step | plan=%s | "
                    "step=%s | type=%s",
                    plan.plan_id,
                    step.id,
                    step.step_type.value,
                )

                try:

                    result = await handler(
                        plan,
                        step,
                    )

                    last_result = result

                    self.successful_steps += 1

                    plan.complete_current_step(
                        result
                    )

                except Exception as exc:

                    self.failed_steps += 1

                    logger.exception(
                        "Plan step failed | "
                        "plan=%s | step=%s",
                        plan.plan_id,
                        step.id,
                    )

                    if step.required:

                        plan.cancel(
                            reason=(
                                f"Step {step.id} "
                                f"failed: {exc}"
                            )
                        )

                        raise

                    # Optional step.
                    plan.complete_current_step(
                        {
                            "success": False,
                            "error": str(exc),
                        }
                    )

            self.successful_executions += 1

            duration = (
                time.monotonic()
                - started
            )

            return ExecutionResult(
                success=plan.completed,
                plan_id=plan.plan_id,
                action=plan.action,
                completed_steps=sum(
                    1
                    for step in plan.steps
                    if step.completed
                ),
                total_steps=len(
                    plan.steps
                ),
                result=last_result,
                error=None
                if plan.completed
                else "plan_not_completed",
                duration_seconds=duration,
            )

        except Exception as exc:

            self.failed_executions += 1

            duration = (
                time.monotonic()
                - started
            )

            return ExecutionResult(
                success=False,
                plan_id=plan.plan_id,
                action=plan.action,
                completed_steps=sum(
                    1
                    for step in plan.steps
                    if step.completed
                ),
                total_steps=len(
                    plan.steps
                ),
                result=last_result,
                error=str(exc),
                duration_seconds=duration,
            )

    # ========================================================
    # DEFAULT HANDLERS
    # ========================================================

    async def _handle_analyze(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "analysis",
            "plan_id": plan.plan_id,
        }

    # ========================================================

    async def _handle_retrieve_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "user_memory",
            "status": "delegated_to_context_system",
        }

    # ========================================================

    async def _handle_retrieve_group_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "group_memory",
            "status": "delegated_to_context_system",
        }

    # ========================================================

    async def _handle_relationship(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "relationship",
            "status": "delegated_to_agent_context",
        }

    # ========================================================

    async def _handle_session_state(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "session_state",
            "status": "delegated_to_agent_context",
        }

    # ========================================================

    async def _handle_generate_response(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "generate_response",
            "status": "waiting_for_ai_engine",
        }

    # ========================================================

    async def _handle_clarification(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "clarification",
            "status": "waiting_for_ai_engine",
        }

    # ========================================================

    async def _handle_save_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "save_memory",
            "status": "delegated_to_memory_system",
        }

    # ========================================================

    async def _handle_create_reminder(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "create_reminder",
            "status": "waiting_for_reminder_service",
        }

    # ========================================================

    async def _handle_use_tool(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "tool",
            "status": "waiting_for_tool_registry",
        }

    # ========================================================

    async def _handle_send_response(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "send_response",
            "status": "waiting_for_telegram_sender",
        }

    # ========================================================

    async def _handle_finish(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "finish",
            "plan_id": plan.plan_id,
        }

    # ========================================================
    # SINGLE STEP
    # ========================================================

    async def execute_step(
        self,
        plan: ExecutionPlan,
    ) -> Any:

        step = plan.get_current_step()

        if step is None:

            return None

        handler = self._handlers.get(
            step.step_type
        )

        if handler is None:

            raise RuntimeError(
                "No handler registered for "
                f"{step.step_type.value}"
            )

        result = await handler(
            plan,
            step,
        )

        self.total_steps += 1
        self.successful_steps += 1

        plan.complete_current_step(
            result
        )

        return result

    # ========================================================
    # STATS
    # ========================================================

    def stats(self) -> dict[str, int]:

        return {
            "total_executions": (
                self.total_executions
            ),
            "successful_executions": (
                self.successful_executions
            ),
            "failed_executions": (
                self.failed_executions
            ),
            "total_steps": (
                self.total_steps
            ),
            "successful_steps": (
                self.successful_steps
            ),
            "failed_steps": (
                self.failed_steps
            ),
            "registered_handlers": len(
                self._handlers
            ),
        }


# ============================================================
# GLOBAL EXECUTOR
# ============================================================

sara_executor = SaraExecutor()
