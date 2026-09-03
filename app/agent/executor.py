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


logger = logging.getLogger(
    "sara.agent.executor"
)


StepHandler = Callable[
    [ExecutionPlan, PlanStep],
    Awaitable[Any],
]


# ================================================================
# EXECUTION RESULT
# ================================================================

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


# ================================================================
# SARA EXECUTOR
# ================================================================

class SaraExecutor:

    def __init__(
        self,
        registry: ToolRegistry | None = None,
    ) -> None:

        self.registry = (
            registry or tool_registry
        )

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

    # ============================================================
    # REGISTER HANDLERS
    # ============================================================

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

    # ============================================================
    # REGISTER ONE HANDLER
    # ============================================================

    def register_handler(
        self,
        step_type: PlanStepType,
        handler: StepHandler,
    ) -> None:

        self._handlers[
            step_type
        ] = handler

    # ============================================================
    # EXECUTE PLAN
    # ============================================================

    async def execute(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:

        started = time.monotonic()

        self.total_executions += 1

        logger.info(
            "Executing plan | "
            "id=%s | action=%s",
            plan.plan_id,
            plan.action.value,
        )

        # --------------------------------------------------------
        # CANCELLED
        # --------------------------------------------------------

        if plan.cancelled:

            return self._result(
                plan=plan,
                success=False,
                error="plan_cancelled",
                started=started,
            )

        # --------------------------------------------------------
        # ALREADY COMPLETED
        # --------------------------------------------------------

        if plan.completed:

            return self._result(
                plan=plan,
                success=True,
                result="already_completed",
                started=started,
            )

        last_result: Any = None

        try:

            # ====================================================
            # STEP LOOP
            # ====================================================

            while not plan.completed:

                if plan.cancelled:

                    raise RuntimeError(
                        "Plan cancelled during execution."
                    )

                step = (
                    plan.get_current_step()
                )

                if step is None:
                    break

                self.total_steps += 1

                handler = (
                    self._handlers.get(
                        step.step_type
                    )
                )

                if handler is None:

                    self.failed_steps += 1

                    raise RuntimeError(
                        "No executor handler for "
                        f"{step.step_type.value}"
                    )

                # =================================================
                # EXECUTE STEP
                # =================================================

                try:

                    result = await handler(
                        plan,
                        step,
                    )

                    # ------------------------------------------------
                    # Check standardized tool result
                    # ------------------------------------------------

                    if isinstance(
                        result,
                        ToolResult,
                    ):

                        if not result.success:

                            if step.required:

                                raise RuntimeError(
                                    result.error
                                    or (
                                        "Tool execution "
                                        "failed."
                                    )
                                )

                    # ------------------------------------------------
                    # Check dict-style result
                    # ------------------------------------------------

                    elif isinstance(
                        result,
                        dict,
                    ):

                        if (
                            result.get(
                                "success"
                            )
                            is False
                            and step.required
                        ):

                            raise RuntimeError(
                                result.get(
                                    "error"
                                )
                                or (
                                    "Step execution "
                                    "failed."
                                )
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

                    # ------------------------------------------------
                    # Optional step failure
                    # ------------------------------------------------

                    plan.complete_current_step(
                        {
                            "success": False,
                            "error": str(exc),
                        }
                    )

            # ====================================================
            # RESULT
            # ====================================================

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

    # ============================================================
    # ANALYZE
    # ============================================================

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

    # ============================================================
    # USER MEMORY
    # ============================================================

    async def _handle_retrieve_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "user_memory",
            "status": (
                "available_through_ai_context"
            ),
            "user_id": step.arguments.get(
                "user_id"
            ),
        }

    # ============================================================
    # GROUP MEMORY
    # ============================================================

    async def _handle_retrieve_group_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "group_memory",
            "status": (
                "available_through_ai_context"
            ),
            "group_id": step.arguments.get(
                "group_id"
            ),
        }

    # ============================================================
    # RELATIONSHIP
    # ============================================================

    async def _handle_relationship(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "relationship",
            "status": (
                "available_through_agent_context"
            ),
            "user_id": step.arguments.get(
                "user_id"
            ),
        }

    # ============================================================
    # SESSION STATE
    # ============================================================

    async def _handle_session_state(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "session_state",
            "status": (
                "available_through_agent_context"
            ),
        }

    # ============================================================
    # GENERATE RESPONSE
    # ============================================================

    async def _handle_generate_response(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        response_text = (
            step.arguments.get(
                "response_text"
            )
            or plan.metadata.get(
                "response_text"
            )
        )

        if not response_text:

            return {
                "success": False,
                "type": "generate_response",
                "error": (
                    "response_text_missing"
                ),
            }

        return {
            "success": True,
            "type": "generate_response",
            "text": response_text,
        }

    # ============================================================
    # CLARIFICATION
    # ============================================================

    async def _handle_clarification(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "type": "clarification",
        }

    # ============================================================
    # SAVE MEMORY
    # ============================================================

    async def _handle_save_memory(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        # --------------------------------------------------------
        # Hozircha Memory Tool alohida keyingi integrationda
        # kuchaytiriladi.
        #
        # Muhim:
        # AI Engine mavjud memory extraction orqali ham
        # memory saqlashi mumkin.
        # --------------------------------------------------------

        return {
            "success": True,
            "type": "save_memory",
            "status": (
                "memory_service_integration_pending"
            ),
            "user_id": step.arguments.get(
                "user_id"
            ),
            "group_id": step.arguments.get(
                "group_id"
            ),
            "text": step.arguments.get(
                "text"
            ),
        }

    # ============================================================
    # CREATE REMINDER
    # ============================================================

    async def _handle_create_reminder(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        owner_telegram_id = step.arguments.get(
            "owner_telegram_id"
        )

        chat_id = step.arguments.get(
            "chat_id"
        )

        text = step.arguments.get(
            "text"
        )

        # --------------------------------------------------------
        # VALIDATION
        # --------------------------------------------------------

        if owner_telegram_id is None:

            return {
                "success": False,
                "type": "create_reminder",
                "error": (
                    "owner_telegram_id_missing"
                ),
            }

        if chat_id is None:

            return {
                "success": False,
                "type": "create_reminder",
                "error": "chat_id_missing",
            }

        if not text:

            return {
                "success": False,
                "type": "create_reminder",
                "error": "reminder_text_missing",
            }

        # --------------------------------------------------------
        # REAL REMINDER TOOL
        # --------------------------------------------------------

        logger.info(
            "Executor calling Reminder Tool | "
            "plan=%s | owner=%s | chat=%s",
            plan.plan_id,
            owner_telegram_id,
            chat_id,
        )

        tool_result = await self.registry.execute(
            "reminder",
            arguments={
                "operation": "create",
                "owner_telegram_id": int(
                    owner_telegram_id
                ),
                "chat_id": int(
                    chat_id
                ),
                "text": str(
                    text
                ),
            },
        )

        # --------------------------------------------------------
        # TOOL FAILED
        # --------------------------------------------------------

        if not tool_result.success:

            logger.warning(
                "Reminder Tool failed | "
                "plan=%s | error=%s",
                plan.plan_id,
                tool_result.error,
            )

            return {
                "success": False,
                "type": "create_reminder",
                "error": (
                    tool_result.error
                    or "reminder_tool_failed"
                ),
            }

        # --------------------------------------------------------
        # TOOL SUCCESS
        # --------------------------------------------------------

        return {
            "success": True,
            "type": "create_reminder",
            "tool": "reminder",
            "result": tool_result.result,
        }

    # ============================================================
    # GENERIC TOOL
    # ============================================================

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

        if not isinstance(
            tool_arguments,
            dict,
        ):

            return ToolResult(
                success=False,
                tool_name=str(
                    tool_name
                ),
                error=(
                    "tool_arguments_must_be_dict"
                ),
            )

        logger.info(
            "Executor calling ToolRegistry | "
            "tool=%s | plan=%s",
            tool_name,
            plan.plan_id,
        )

        result = await self.registry.execute(
            str(tool_name),
            arguments=tool_arguments,
        )

        if not result.success:

            logger.warning(
                "Tool failed | "
                "tool=%s | error=%s",
                tool_name,
                result.error,
            )

        return result

    # ============================================================
    # SEND TELEGRAM RESPONSE
    # ============================================================

    async def _handle_send_response(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> dict[str, Any]:

        chat_id = step.arguments.get(
            "chat_id"
        )

        text = (
            step.arguments.get(
                "text"
            )
            or plan.metadata.get(
                "response_text"
            )
        )

        reply_to_message_id = (
            step.arguments.get(
                "reply_to_message_id"
            )
        )

        # --------------------------------------------------------
        # VALIDATION
        # --------------------------------------------------------

        if chat_id is None:

            return {
                "success": False,
                "type": "telegram_send_message",
                "error": "chat_id_missing",
            }

        if not text:

            return {
                "success": False,
                "type": "telegram_send_message",
                "error": (
                    "response_text_missing"
                ),
            }

        # --------------------------------------------------------
        # TELEGRAM TOOL
        # --------------------------------------------------------

        result = await self.registry.execute(
            "telegram_send_message",
            arguments={
                "chat_id": int(
                    chat_id
                ),
                "text": str(
                    text
                ),
                "reply_to_message_id": (
                    reply_to_message_id
                ),
            },
        )

        if not result.success:

            logger.warning(
                "Telegram send failed | "
                "plan=%s | error=%s",
                plan.plan_id,
                result.error,
            )

            return {
                "success": False,
                "type": "telegram_send_message",
                "error": (
                    result.error
                    or "telegram_send_failed"
                ),
            }

        return {
            "success": True,
            "type": "telegram_send_message",
            "result": result.result,
        }

    # ============================================================
    # FINISH
    # ============================================================

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

    # ============================================================
    # EXECUTE SINGLE STEP
    # ============================================================

    async def execute_step(
        self,
        plan: ExecutionPlan,
    ) -> Any:

        step = (
            plan.get_current_step()
        )

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

        # --------------------------------------------------------
        # Failed required result
        # --------------------------------------------------------

        if isinstance(
            result,
            ToolResult,
        ):

            if not result.success:

                raise RuntimeError(
                    result.error
                    or "Tool failed."
                )

        elif isinstance(
            result,
            dict,
        ):

            if result.get(
                "success"
            ) is False:

                raise RuntimeError(
                    result.get(
                        "error"
                    )
                    or "Step failed."
                )

        self.total_steps += 1

        self.successful_steps += 1

        plan.complete_current_step(
            result
        )

        return result

    # ============================================================
    # RESULT
    # ============================================================

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
            total_steps=len(
                plan.steps
            ),
            result=result,
            error=error,
            duration_seconds=(
                time.monotonic()
                - started
            ),
        )

    # ============================================================
    # STATS
    # ============================================================

    def stats(
        self,
    ) -> dict[str, int]:

        return {

            "total_executions":
                self.total_executions,

            "successful_executions":
                self.successful_executions,

            "failed_executions":
                self.failed_executions,

            "total_steps":
                self.total_steps,

            "successful_steps":
                self.successful_steps,

            "failed_steps":
                self.failed_steps,

            "registered_handlers":
                len(self._handlers),

        }


# ================================================================
# GLOBAL EXECUTOR
# ================================================================

sara_executor = SaraExecutor()
