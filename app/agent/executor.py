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
from app.agent.tool_registry import (
    ToolRegistry,
    ToolResult,
    tool_registry,
)

logger = logging.getLogger("sara.agent.executor")


StepHandler = Callable[
    [ExecutionPlan, PlanStep],
    Awaitable[Any],
]


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


class SaraExecutor:

    def __init__(
        self,
        registry: ToolRegistry | None = None,
    ) -> None:

        self.registry = registry or tool_registry

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

    # =========================================================
    # HANDLERS
    # =========================================================

    def _register_default_handlers(self) -> None:

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

    def register_handler(
        self,
        step_type: PlanStepType,
        handler: StepHandler,
    ) -> None:

        self._handlers[step_type] = handler

    # =========================================================
    # EXECUTE PLAN
    # =========================================================

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

            return self._result(
                plan=plan,
                success=False,
                error="plan_cancelled",
                started=started,
            )

        if plan.completed:

            return self._result(
                plan=plan,
                success=True,
                result="already_completed",
                started=started,
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
                        "Plan step failed | plan=%s | step=%s",
                        plan.plan_id,
                        step.id,
                    )

                    if step.required:

                        plan.cancel(
                            reason=(
                                f"Step {step.id} failed: "
                                f"{exc}"
                            )
                        )

                        raise

                    plan.complete_current_step(
                        {
                            "success": False,
                            "error": str(exc),
                        }
                    )

            success = plan.completed

            if success:
                self.successful_executions += 1
            else:
                self.failed_executions += 1

            return self._result(
                plan=plan,
                success=success,
                result=last_result,
                error=(
                    None
                    if success
                    else "plan_not_completed"
                ),
                started=started,
            )

        except Exception as exc:

            self.failed_executions += 1

            return self._result(
                plan=plan,
                success=False,
                result=last_result,
                error=str(exc),
                started=started,
            )

    # =========================================================
    # STEP HANDLERS
    # =========================================================

    async def _handle_analyze(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "analysis",
            "text": plan.user_text,
        }

    async def _handle_retrieve_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "user_memory",
            "status": "available_through_ai_context",
        }

    async def _handle_retrieve_group_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "group_memory",
            "status": "available_through_ai_context",
        }

    async def _handle_relationship(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "relationship",
            "status": "available_through_agent_context",
        }

    async def _handle_session_state(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "session_state",
            "status": "available_through_agent_context",
        }

    async def _handle_generate_response(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        response_text = (
            step.arguments.get("response_text")
            or plan.metadata.get("response_text")
        )

        return {
            "success": True,
            "type": "generate_response",
            "text": response_text,
        }

    async def _handle_clarification(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "clarification",
        }

    async def _handle_save_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "save_memory",
            "status": "memory_service_integration_pending",
            "text": step.arguments.get("text"),
        }

    async def _handle_create_reminder(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "create_reminder",
            "status": "reminder_service_integration_pending",
            "text": step.arguments.get("text"),
        }

    # =========================================================
    # REAL TOOL EXECUTION
    # =========================================================

    async def _handle_use_tool(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> ToolResult:

        tool_name = step.arguments.get(
            "tool_name"
        )

        tool_arguments = step.arguments.get(
            "tool_arguments",
            {},
        )

        if not tool_name:

            return ToolResult(
                success=False,
                tool_name="",
                error="tool_name_missing",
            )

        logger.info(
            "Executor calling ToolRegistry | "
            "tool=%s | plan=%s",
            tool_name,
            plan.plan_id,
        )

        result = await self.registry.execute(
            tool_name,
            arguments=tool_arguments,
        )

        if not result.success:

            logger.warning(
                "Tool failed | tool=%s | error=%s",
                tool_name,
                result.error,
            )

        return result

    # =========================================================
    # REAL TELEGRAM SEND
    # =========================================================

    async def _handle_send_response(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        chat_id = step.arguments.get(
            "chat_id"
        )

        text = (
            step.arguments.get("text")
            or plan.metadata.get("response_text")
        )

        reply_to_message_id = step.arguments.get(
            "reply_to_message_id"
        )

        if not chat_id:
            return {
                "success": False,
                "error": "chat_id_missing",
            }

        if not text:
            return {
                "success": False,
                "error": "response_text_missing",
            }

        result = await self.registry.execute(
            "telegram_send_message",
            arguments={
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": reply_to_message_id,
            },
        )

        return {
            "success": result.success,
            "type": "telegram_send_message",
            "result": result.result,
            "error": result.error,
        }

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

    # =========================================================
    # EXECUTE SINGLE STEP
    # =========================================================

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

    # =========================================================
    # RESULT
    # =========================================================

    def _result(
        self,
        *,
        plan: ExecutionPlan,
        success: bool,
        started: float,
        result: Any = None,
        error: str | None = None,
    ) -> ExecutionResult:

        return ExecutionResult(
            success=success,
            plan_id=plan.plan_id,
            action=plan.action,
            completed_steps=sum(
                1
                for step in plan.steps
                if step.completed
            ),
            total_steps=len(plan.steps),
            result=result,
            error=error,
            duration_seconds=(
                time.monotonic() - started
            ),
        )

    # =========================================================
    # STATS
    # =========================================================

    def stats(self) -> dict[str, int]:

        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "total_steps": self.total_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "registered_handlers": len(
                self._handlers
            ),
        }


sara_executor = SaraExecutor()
