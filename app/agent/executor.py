from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.agent.planner import ExecutionPlan, PlanStep, PlanStepType
from app.agent.tools.memory_tool import memory_tool_handler
from app.agent.tools.reminder_tool import reminder_tool_handler
from app.agent.tools.registry import ToolResult, tool_registry
from app.agent.tools.telegram_tool import send_telegram_message

logger = logging.getLogger("sara.agent.executor")


# ================================================================
# EXECUTION RESULT
# ================================================================

@dataclass
class ExecutionResult:
    success: bool
    response_text: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def completed_steps(self) -> int:
        return sum(
            1
            for step in self.steps
            if step.get("completed") is True
        )

    @property
    def failed_steps(self) -> int:
        return sum(
            1
            for step in self.steps
            if step.get("error")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "response_text": self.response_text,
            "steps": self.steps,
            "error": self.error,
            "metadata": self.metadata,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
        }


# ================================================================
# SARA EXECUTOR
# ================================================================

class SaraExecutor:
    """
    SARA Agent Executor.

    Planner yaratgan ExecutionPlan'ni bajaradi.

    Pipeline:

        Brain
          ↓
        Planner
          ↓
        Executor
          ↓
        Tools / Memory / Reminder / Telegram
    """

    def __init__(self) -> None:
        self._executed_plans = 0
        self._successful_plans = 0
        self._failed_plans = 0

    # ============================================================
    # MAIN EXECUTION
    # ============================================================

    async def execute(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:

        started = time.monotonic()

        try:
            self._validate_plan(plan)

            logger.info(
                "Executing SARA plan | id=%s | action=%s | steps=%s",
                plan.plan_id,
                plan.action,
                len(plan.steps),
            )

            response_text = ""
            execution_steps: list[dict[str, Any]] = []

            while not plan.completed and not plan.cancelled:

                step = plan.get_current_step()

                if step is None:
                    break

                try:
                    result = await self._execute_step(
                        plan,
                        step,
                    )

                    normalized = self._normalize_tool_result(result)

                    # ------------------------------------------------
                    # RESPONSE TEXT
                    # ------------------------------------------------

                    step_response = normalized.get(
                        "response_text",
                        "",
                    )

                    if step_response:
                        response_text = str(step_response).strip()

                    # ------------------------------------------------
                    # TELEGRAM SEND STATUS
                    # ------------------------------------------------

                    if normalized.get("telegram_sent"):
                        plan.metadata["telegram_sent"] = True

                        if normalized.get("telegram_message_id"):
                            plan.metadata[
                                "telegram_message_id"
                            ] = normalized[
                                "telegram_message_id"
                            ]

                    # ------------------------------------------------
                    # STEP SUCCESS
                    # ------------------------------------------------

                    step.complete(normalized)

                    execution_steps.append(
                        step.to_dict()
                    )

                    plan.complete_current_step(
                        normalized
                    )

                except Exception as exc:

                    logger.exception(
                        "SARA step failed | plan=%s | step=%s",
                        plan.plan_id,
                        step.id,
                    )

                    step.fail(str(exc))

                    execution_steps.append(
                        step.to_dict()
                    )

                    plan.fail_current_step(
                        str(exc)
                    )

                    if step.required:
                        error = str(exc)

                        self._failed_plans += 1

                        return ExecutionResult(
                            success=False,
                            response_text=response_text,
                            steps=execution_steps,
                            error=error,
                            metadata=self._execution_metadata(
                                plan=plan,
                                started=started,
                            ),
                        )

            # --------------------------------------------------------
            # FINISHED
            # --------------------------------------------------------

            self._executed_plans += 1

            if plan.cancelled:
                self._failed_plans += 1

                return ExecutionResult(
                    success=False,
                    response_text=response_text,
                    steps=execution_steps,
                    error=plan.cancel_reason or "plan_cancelled",
                    metadata=self._execution_metadata(
                        plan=plan,
                        started=started,
                    ),
                )

            self._successful_plans += 1

            return ExecutionResult(
                success=True,
                response_text=response_text,
                steps=execution_steps,
                metadata=self._execution_metadata(
                    plan=plan,
                    started=started,
                ),
            )

        except Exception as exc:

            self._failed_plans += 1

            logger.exception(
                "SARA plan execution failed | plan=%s",
                getattr(plan, "plan_id", "unknown"),
            )

            return ExecutionResult(
                success=False,
                error=str(exc),
                metadata={
                    "plan_id": getattr(
                        plan,
                        "plan_id",
                        None,
                    ),
                    "duration_seconds": round(
                        time.monotonic() - started,
                        4,
                    ),
                },
            )

    # ============================================================
    # STEP EXECUTION
    # ============================================================

    async def _execute_step(
        self,
        plan: ExecutionPlan,
        step: PlanStep,
    ) -> Any:

        step_type = step.step_type

        # ----------------------------------------------------------
        # ANALYZE
        # ----------------------------------------------------------

        if step_type == PlanStepType.ANALYZE:

            return {
                "success": True,
                "analysis": {
                    "action": plan.action,
                    "user_text": plan.user_text,
                    "chat_id": plan.metadata.get("chat_id"),
                    "user_id": plan.metadata.get("user_id"),
                    "group_id": plan.metadata.get("group_id"),
                },
            }

        # ----------------------------------------------------------
        # USER MEMORY
        # ----------------------------------------------------------

        if step_type == PlanStepType.RETRIEVE_MEMORY:

            args = dict(step.arguments or {})

            user_id = args.get(
                "user_telegram_id"
            )

            query = args.get(
                "query",
                plan.user_text,
            )

            limit = args.get(
                "limit",
                10,
            )

            if user_id is None:
                return {
                    "success": False,
                    "error": "missing_user_telegram_id",
                }

            result = await memory_tool_handler(
                operation="search_user",
                user_telegram_id=int(user_id),
                query=str(query or ""),
                limit=int(limit),
            )

            return result

        # ----------------------------------------------------------
        # GROUP MEMORY
        # ----------------------------------------------------------

        if step_type == PlanStepType.RETRIEVE_GROUP_MEMORY:

            args = dict(step.arguments or {})

            group_id = args.get(
                "group_telegram_id"
            )

            query = args.get(
                "query",
                plan.user_text,
            )

            limit = args.get(
                "limit",
                10,
            )

            if group_id is None:
                return {
                    "success": False,
                    "error": "missing_group_telegram_id",
                }

            result = await memory_tool_handler(
                operation="search_group",
                group_telegram_id=int(group_id),
                query=str(query or ""),
                limit=int(limit),
            )

            return result

        # ----------------------------------------------------------
        # RELATIONSHIP
        # ----------------------------------------------------------

        if step_type == PlanStepType.CHECK_RELATIONSHIP:

            return {
                "success": True,
                "relationship": plan.metadata.get(
                    "relationship_context",
                    {},
                ),
            }

        # ----------------------------------------------------------
        # SESSION STATE
        # ----------------------------------------------------------

        if step_type == PlanStepType.CHECK_SESSION_STATE:

            return {
                "success": True,
                "session_state": plan.metadata.get(
                    "session_state",
                    {},
                ),
            }

        # ----------------------------------------------------------
        # GENERATE RESPONSE
        # ----------------------------------------------------------

        if step_type == PlanStepType.GENERATE_RESPONSE:

            response_text = str(
                plan.metadata.get(
                    "response_text",
                    "",
                )
                or ""
            ).strip()

            return {
                "success": bool(response_text),
                "response_text": response_text,
            }

        # ----------------------------------------------------------
        # ASK CLARIFICATION
        # ----------------------------------------------------------

        if step_type == PlanStepType.ASK_CLARIFICATION:

            response_text = str(
                plan.metadata.get(
                    "response_text",
                    "",
                )
                or ""
            ).strip()

            if not response_text:
                response_text = (
                    "Aniqroq tushuntirib bera olasanmi? "
                    "Nimani nazarda tutganingni bilsam, yaxshiroq yordam beraman."
                )

            return {
                "success": True,
                "response_text": response_text,
            }

        # ----------------------------------------------------------
        # SAVE MEMORY
        # ----------------------------------------------------------

        if step_type == PlanStepType.SAVE_MEMORY:

            args = dict(step.arguments or {})

            text = str(
                args.get(
                    "text",
                    plan.user_text,
                )
                or ""
            ).strip()

            if not text:
                return {
                    "success": False,
                    "error": "empty_memory_text",
                }

            user_id = args.get(
                "user_telegram_id"
            )

            group_id = args.get(
                "group_telegram_id"
            )

            memory_type = str(
                args.get(
                    "memory_type",
                    "important_fact",
                )
            )

            importance = float(
                args.get(
                    "importance",
                    0.8,
                )
            )

            confidence = float(
                args.get(
                    "confidence",
                    0.9,
                )
            )

            source_message_id = args.get(
                "source_message_id"
            )

            # GROUP MEMORY
            if group_id is not None:

                return await memory_tool_handler(
                    operation="save_group",
                    group_telegram_id=int(group_id),
                    memory_type=memory_type,
                    content=text,
                    importance=importance,
                    confidence=confidence,
                    source_message_id=source_message_id,
                )

            # USER MEMORY
            if user_id is not None:

                return await memory_tool_handler(
                    operation="save_user",
                    user_telegram_id=int(user_id),
                    memory_type=memory_type,
                    content=text,
                    importance=importance,
                    confidence=confidence,
                    source_message_id=source_message_id,
                )

            return {
                "success": False,
                "error": "missing_memory_owner",
            }

        # ----------------------------------------------------------
        # REMINDER
        # ----------------------------------------------------------

        if step_type == PlanStepType.CREATE_REMINDER:

            args = dict(step.arguments or {})

            owner_id = args.get(
                "owner_telegram_id"
            )

            chat_id = args.get(
                "chat_id"
            )

            text = str(
                args.get(
                    "text",
                    plan.user_text,
                )
                or ""
            ).strip()

            if owner_id is None:
                return {
                    "success": False,
                    "error": "missing_reminder_owner",
                }

            if chat_id is None:
                return {
                    "success": False,
                    "error": "missing_reminder_chat_id",
                }

            return await reminder_tool_handler(
                operation="create",
                owner_telegram_id=int(owner_id),
                chat_id=int(chat_id),
                text=text,
            )

        # ----------------------------------------------------------
        # GENERIC TOOL
        # ----------------------------------------------------------

        if step_type == PlanStepType.USE_TOOL:

            args = dict(step.arguments or {})

            tool_name = args.pop(
                "tool_name",
                None,
            )

            tool_arguments = args.pop(
                "tool_arguments",
                {},
            )

            if not tool_name:
                return {
                    "success": False,
                    "error": "missing_tool_name",
                }

            if not isinstance(
                tool_arguments,
                dict,
            ):
                tool_arguments = {}

            return await tool_registry.execute(
                str(tool_name),
                **tool_arguments,
            )

        # ----------------------------------------------------------
        # TELEGRAM RESPONSE
        # ----------------------------------------------------------

        if step_type == PlanStepType.SEND_RESPONSE:

            args = dict(step.arguments or {})

            chat_id = args.get(
                "chat_id",
                plan.metadata.get("chat_id"),
            )

            text = str(
                args.get(
                    "text",
                    plan.metadata.get(
                        "response_text",
                        "",
                    ),
                )
                or ""
            ).strip()

            reply_to_message_id = args.get(
                "reply_to_message_id",
                plan.metadata.get(
                    "reply_to_message_id"
                ),
            )

            if chat_id is None:
                return {
                    "success": False,
                    "error": "missing_chat_id",
                }

            if not text:
                return {
                    "success": False,
                    "error": "empty_response",
                }

            result = await send_telegram_message(
                chat_id=int(chat_id),
                text=text,
                reply_to_message_id=(
                    int(reply_to_message_id)
                    if reply_to_message_id is not None
                    else None
                ),
            )

            normalized = self._normalize_tool_result(
                result
            )

            # =====================================================
            # MUHIM:
            # Telegram muvaffaqiyatli yuborilganini plan metadata'ga
            # yozamiz.
            #
            # Handler shu flag orqali ikkinchi marta yubormaydi.
            # =====================================================

            if normalized.get("success"):

                normalized["telegram_sent"] = True

                if normalized.get(
                    "message_id"
                ) is not None:

                    normalized[
                        "telegram_message_id"
                    ] = int(
                        normalized["message_id"]
                    )

                plan.metadata[
                    "telegram_sent"
                ] = True

                if normalized.get(
                    "telegram_message_id"
                ):

                    plan.metadata[
                        "telegram_message_id"
                    ] = normalized[
                        "telegram_message_id"
                    ]

            normalized["response_text"] = text

            return normalized

        # ----------------------------------------------------------
        # FINISH
        # ----------------------------------------------------------

        if step_type == PlanStepType.FINISH:

            return {
                "success": True,
                "finished": True,
            }

        # ----------------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------------

        return {
            "success": False,
            "error": f"unknown_plan_step:{step_type}",
        }

    # ============================================================
    # VALIDATION
    # ============================================================

    def _validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> None:

        if plan is None:
            raise ValueError(
                "ExecutionPlan is required."
            )

        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan must be an ExecutionPlan."
            )

        if not plan.plan_id:
            raise ValueError(
                "Plan ID is required."
            )

        if not isinstance(
            plan.steps,
            list,
        ):
            raise TypeError(
                "Plan steps must be a list."
            )

    # ============================================================
    # TOOL RESULT NORMALIZATION
    # ============================================================

    def _normalize_tool_result(
        self,
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            ToolResult,
        ):

            data = result.result

            normalized: dict[str, Any] = {
                "success": bool(
                    result.success
                ),
                "tool_name": result.tool_name,
                "duration_seconds": result.duration_seconds,
            }

            if isinstance(
                data,
                dict,
            ):
                normalized.update(data)

            elif data is not None:
                normalized["result"] = data

            if result.error:
                normalized["error"] = result.error

            return normalized

        if isinstance(
            result,
            dict,
        ):
            return dict(result)

        if result is None:
            return {
                "success": True,
            }

        return {
            "success": True,
            "result": result,
        }

    # ============================================================
    # METADATA
    # ============================================================

    def _execution_metadata(
        self,
        *,
        plan: ExecutionPlan,
        started: float,
    ) -> dict[str, Any]:

        return {
            "plan_id": plan.plan_id,
            "action": plan.action,
            "progress": plan.progress(),
            "duration_seconds": round(
                time.monotonic() - started,
                4,
            ),
            "completed": bool(
                plan.completed
            ),
            "cancelled": bool(
                plan.cancelled
            ),
            "telegram_sent": bool(
                plan.metadata.get(
                    "telegram_sent",
                    False,
                )
            ),
            "telegram_message_id": plan.metadata.get(
                "telegram_message_id"
            ),
        }

    # ============================================================
    # SAFE HELPERS
    # ============================================================

    @staticmethod
    def _safe_result(
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            dict,
        ):
            return result

        return {
            "success": True,
            "result": result,
        }

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 0,
    ) -> int:

        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # ============================================================
    # STATS
    # ============================================================

    def stats(self) -> dict[str, Any]:

        return {
            "executed_plans": self._executed_plans,
            "successful_plans": self._successful_plans,
            "failed_plans": self._failed_plans,
        }

    def reset_stats(self) -> None:

        self._executed_plans = 0
        self._successful_plans = 0
        self._failed_plans = 0


# ================================================================
# GLOBAL EXECUTOR
# ================================================================

sara_executor = SaraExecutor()


__all__ = [
    "ExecutionResult",
    "SaraExecutor",
    "sara_executor",
]
