from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.agent.brain import (
    ActionType,
    BrainDecision,
    BrainInput,
    sara_brain,
)
from app.agent.executor import (
    ExecutionResult,
    sara_executor,
)
from app.agent.planner import (
    ExecutionPlan,
    sara_planner,
)
from app.agent.runtime import AgentRuntimeContext
from app.ai.engine import ai_engine
from app.ai.models import AIResponse


logger = logging.getLogger("sara.agent.orchestrator")


# ============================================================
# RESULT
# ============================================================

@dataclass
class AgentRunResult:
    success: bool = False

    decision: BrainDecision | None = None
    plan: ExecutionPlan | None = None
    execution: ExecutionResult | None = None

    response_text: str = ""

    should_send: bool = False

    error: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# ORCHESTRATOR
# ============================================================

class SaraOrchestrator:

    def __init__(self) -> None:
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        self.ignored_runs = 0

    # ========================================================
    # PROCESS
    # ========================================================

    async def process(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        user_text: str,
        group_id: int | None = None,
        reply_to_message_id: int | None = None,
        is_group: bool = False,
        is_private: bool = False,
        is_bot_message: bool = False,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        is_question: bool = False,
        proactive_allowed: bool = False,
        extra_flags: dict[str, Any] | None = None,
    ) -> AgentRunResult:

        self.total_runs += 1

        flags = dict(
            extra_flags or {}
        )

        runtime: AgentRuntimeContext | None = None

        try:

            # ==================================================
            # 1. RUNTIME
            # ==================================================

            runtime = AgentRuntimeContext(
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,

                is_private=is_private,
                is_group=is_group,

                is_bot_message=is_bot_message,

                sara_called=sara_called,
                is_reply_to_sara=is_reply_to_sara,
                is_question=is_question,

                proactive_allowed=proactive_allowed,
            )

            await runtime.prepare(
                user_text=user_text,
                extra_flags=flags,
            )

            # ==================================================
            # 2. CONTEXT
            # ==================================================

            agent_context = self._runtime_to_context(
                runtime=runtime,
                extra_flags=flags,
            )

            # ==================================================
            # 3. BRAIN INPUT
            # ==================================================

            brain_input = BrainInput(
                context=agent_context,
                user_text=user_text,
                flags={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "group_id": group_id,

                    "is_group": is_group,
                    "is_private": is_private,
                    "is_bot_message": is_bot_message,

                    "sara_called": sara_called,
                    "is_reply_to_sara": is_reply_to_sara,
                    "is_question": is_question,

                    "proactive_allowed": (
                        proactive_allowed
                    ),

                    **flags,
                },
            )

            # ==================================================
            # 4. BRAIN
            # ==================================================

            decision = await sara_brain.decide(
                brain_input
            )

            logger.info(
                "Brain decision | chat=%s | user=%s | "
                "action=%s | priority=%s | confidence=%.2f",
                chat_id,
                user_id,
                getattr(decision, "action", None),
                getattr(decision, "priority", None),
                float(
                    getattr(
                        decision,
                        "confidence",
                        0.0,
                    )
                    or 0.0
                ),
            )

            # ==================================================
            # 5. IGNORE
            # ==================================================

            if not decision.should_respond:

                self.ignored_runs += 1

                await runtime.finalize(
                    response_text="",
                    success=True,
                )

                return AgentRunResult(
                    success=True,
                    decision=decision,
                    should_send=False,
                    metadata={
                        "status": "ignored",
                        "reason": getattr(
                            decision,
                            "reason",
                            "",
                        ),
                    },
                )

            # ==================================================
            # 6. AI
            # ==================================================

            response_text = ""

            if self._requires_ai_response(
                decision
            ):

                ai_result: AIResponse = (
                    await ai_engine.generate(
                        chat_id=chat_id,
                        user_id=user_id,
                        user_text=user_text,
                        group_id=group_id,
                        reply_to_message_id=(
                            reply_to_message_id
                        ),
                        is_group=is_group,
                        is_private=is_private,
                        is_bot_message=is_bot_message,
                        sara_called=sara_called,
                        is_reply_to_sara=is_reply_to_sara,
                        is_question=is_question,
                        extra_flags={
                            **flags,
                            "brain_action": str(
                                decision.action
                            ),
                            "brain_priority": str(
                                decision.priority
                            ),
                            "brain_confidence": getattr(
                                decision,
                                "confidence",
                                0.0,
                            ),
                            "brain_reason": getattr(
                                decision,
                                "reason",
                                "",
                            ),
                            "proactive_allowed": (
                                proactive_allowed
                            ),
                            "agent_context": (
                                runtime.agent_context
                            ),
                            "privacy_context": (
                                runtime.privacy_context
                            ),
                        },
                    )
                )

                response_text = str(
                    ai_result.text or ""
                ).strip()

            # ==================================================
            # 7. PLAN
            # ==================================================

            plan = await sara_planner.create_plan(
                decision=decision,
                user_text=user_text,
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,
                reply_to_message_id=reply_to_message_id,
                response_text=response_text,
                metadata={
                    "is_group": is_group,
                    "is_private": is_private,
                    "is_bot_message": is_bot_message,
                    "sara_called": sara_called,
                    "is_reply_to_sara": is_reply_to_sara,
                    "is_question": is_question,
                    "proactive_allowed": (
                        proactive_allowed
                    ),
                    **flags,
                },
            )

            # ==================================================
            # 8. ATTACH RUNTIME
            # ==================================================

            self._attach_runtime_data(
                plan=plan,
                decision=decision,
                response_text=response_text,
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,
                reply_to_message_id=(
                    reply_to_message_id
                ),
            )

            # ==================================================
            # 9. EXECUTE
            # ==================================================

            execution = await sara_executor.execute(
                plan
            )

            execution_success = bool(
                getattr(
                    execution,
                    "success",
                    False,
                )
            )

            execution_response = str(
                getattr(
                    execution,
                    "response_text",
                    "",
                )
                or ""
            ).strip()

            if execution_response:
                response_text = execution_response

            # ==================================================
            # 10. SEND POLICY
            # ==================================================

            should_send = bool(
                response_text
                and execution_success
                and self._should_send_after_execution(
                    decision=decision,
                    execution=execution,
                )
            )

            # ==================================================
            # 11. FINALIZE
            # ==================================================

            await runtime.finalize(
                response_text=response_text,
                success=execution_success,
            )

            # ==================================================
            # 12. STATS
            # ==================================================

            if execution_success:
                self.successful_runs += 1
            else:
                self.failed_runs += 1

            return AgentRunResult(
                success=execution_success,
                decision=decision,
                plan=plan,
                execution=execution,
                response_text=response_text,
                should_send=should_send,
                metadata={
                    "status": (
                        "completed"
                        if execution_success
                        else "execution_failed"
                    ),
                    "brain_action": str(
                        decision.action
                    ),
                    "brain_priority": str(
                        decision.priority
                    ),
                    "brain_confidence": getattr(
                        decision,
                        "confidence",
                        0.0,
                    ),
                    "brain_reason": getattr(
                        decision,
                        "reason",
                        "",
                    ),
                },
            )

        except Exception as exc:

            self.failed_runs += 1

            logger.exception(
                "SARA Agent pipeline failed | "
                "chat=%s | user=%s | group=%s",
                chat_id,
                user_id,
                group_id,
            )

            if runtime is not None:

                try:
                    await runtime.finalize(
                        response_text="",
                        success=False,
                    )
                except Exception:
                    logger.exception(
                        "Runtime error finalization failed."
                    )

            return AgentRunResult(
                success=False,
                response_text="",
                should_send=False,
                error=str(exc),
                metadata={
                    "status": "error",
                },
            )

    # ========================================================
    # AI POLICY
    # ========================================================

    @staticmethod
    def _requires_ai_response(
        decision: BrainDecision,
    ) -> bool:

        return decision.action in {
            ActionType.RESPOND,
            ActionType.ASK_CLARIFICATION,
            ActionType.CONTINUE_CONVERSATION,
            ActionType.PROACTIVE_MESSAGE,
            ActionType.REMEMBER,
            ActionType.REMINDER,
            ActionType.USE_TOOL,
        }

    # ========================================================
    # SEND POLICY
    # ========================================================

    @staticmethod
    def _should_send_after_execution(
        *,
        decision: BrainDecision,
        execution: ExecutionResult,
    ) -> bool:

        if not getattr(
            execution,
            "success",
            False,
        ):
            return False

        if not decision.should_respond:
            return False

        return True

    # ========================================================
    # ATTACH DATA
    # ========================================================

    @staticmethod
    def _attach_runtime_data(
        *,
        plan: ExecutionPlan,
        decision: BrainDecision,
        response_text: str,
        chat_id: int,
        user_id: int | None,
        group_id: int | None,
        reply_to_message_id: int | None,
    ) -> None:

        metadata = getattr(
            plan,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}
            plan.metadata = metadata

        metadata.update(
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "group_id": group_id,
                "reply_to_message_id": (
                    reply_to_message_id
                ),
                "response_text": response_text,

                "brain_action": str(
                    decision.action
                ),

                "brain_priority": str(
                    decision.priority
                ),

                "brain_confidence": getattr(
                    decision,
                    "confidence",
                    0.0,
                ),

                "brain_reason": getattr(
                    decision,
                    "reason",
                    "",
                ),
            }
        )

        metadata.setdefault(
            "source_text",
            getattr(
                plan,
                "user_text",
                "",
            ),
        )

    # ========================================================
    # RUNTIME → CONTEXT
    # ========================================================

    @staticmethod
    def _runtime_to_context(
        *,
        runtime: AgentRuntimeContext,
        extra_flags: dict[str, Any],
    ) -> dict[str, Any]:

        context = {
            "chat_id": runtime.chat_id,
            "user_id": runtime.user_id,
            "group_id": runtime.group_id,

            "is_group": runtime.is_group,
            "is_private": runtime.is_private,
            "is_bot_message": runtime.is_bot_message,

            "sara_called": runtime.sara_called,
            "is_reply_to_sara": (
                runtime.is_reply_to_sara
            ),

            "is_question": runtime.is_question,

            "proactive_allowed": (
                runtime.proactive_allowed
            ),

            "agent_context": (
                runtime.agent_context
            ),

            "privacy_context": (
                runtime.privacy_context
            ),

            "can_use_private_memory": (
                runtime.can_use_private_memory
            ),

            "can_use_group_memory": (
                runtime.can_use_group_memory
            ),
        }

        try:

            runtime_context = (
                runtime.build_agent_context()
            )

            if isinstance(
                runtime_context,
                dict,
            ):
                context.update(
                    runtime_context
                )

        except Exception:

            logger.exception(
                "Could not build runtime agent context."
            )

        context.update(
            extra_flags
        )

        return context

    # ========================================================
    # STATS
    # ========================================================

    def stats(self) -> dict[str, int]:

        return {
            "total_runs": self.total_runs,
            "successful_runs": (
                self.successful_runs
            ),
            "failed_runs": self.failed_runs,
            "ignored_runs": self.ignored_runs,
        }

    def reset_stats(self) -> None:

        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        self.ignored_runs = 0


# ============================================================
# GLOBAL
# ============================================================

sara_orchestrator = SaraOrchestrator()


__all__ = [
    "AgentRunResult",
    "SaraOrchestrator",
    "sara_orchestrator",
            ]
