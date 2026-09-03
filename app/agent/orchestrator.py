from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.agent.brain import (
    BrainInput,
    BrainDecision,
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
from app.agent.runtime import (
    AgentRuntimeContext,
    agent_runtime,
)
from app.ai.engine import ai_engine

logger = logging.getLogger("sara.agent.orchestrator")


@dataclass
class AgentRunResult:
    """
    SARA Agent ishlashining yakuniy natijasi.
    """

    success: bool

    decision: BrainDecision | None = None

    plan: ExecutionPlan | None = None

    execution: ExecutionResult | None = None

    response_text: str = ""

    should_send: bool = False

    error: str | None = None

    metadata: dict[str, Any] | None = None


class SaraOrchestrator:
    """
    SARA AI Agent'ning asosiy boshqaruv markazi.

    Oqim:

        Telegram
            ↓
        Runtime
            ↓
        Brain
            ↓
        Planner
            ↓
        AI Engine / Tools
            ↓
        Executor
            ↓
        Action
    """

    def __init__(self) -> None:
        self.brain = sara_brain
        self.planner = sara_planner
        self.executor = sara_executor
        self.runtime = agent_runtime

    async def process(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        user_text: str,
        group_id: int | None = None,
        reply_to_message_id: int | None = None,
        message_id: int | None = None,
        is_group: bool = False,
        is_private: bool = False,
        is_bot_message: bool = False,
        sara_called: bool = False,
        is_reply_to_sara: bool = False,
        is_question: bool = False,
        proactive_allowed: bool = True,
        extra_flags: dict[str, Any] | None = None,
    ) -> AgentRunResult:
        """
        Bitta Telegram xabarini SARA Agent orqali qayta ishlaydi.
        """

        try:
            # ==========================================================
            # 1. RUNTIME
            # ==========================================================

            runtime_context = await self.runtime.prepare(
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,
                user_text=user_text,
                is_group=is_group,
                is_private=is_private,
                is_bot_message=is_bot_message,
                sara_called=sara_called,
                is_reply_to_sara=is_reply_to_sara,
            )

            # ==========================================================
            # 2. BRAIN INPUT
            # ==========================================================

            flags: dict[str, Any] = {
                "is_group": is_group,
                "is_private": is_private,
                "is_bot_message": is_bot_message,
                "sara_called": sara_called,
                "is_reply_to_sara": is_reply_to_sara,
                "is_question": is_question,
                "proactive_allowed": proactive_allowed,
            }

            if extra_flags:
                flags.update(extra_flags)

            brain_input = BrainInput(
                context=self._runtime_to_context(
                    runtime_context
                ),
                user_text=user_text,
                flags=flags,
            )

            # ==========================================================
            # 3. BRAIN
            # ==========================================================

            decision = await self.brain.decide(
                brain_input
            )

            logger.info(
                "Brain decision | chat=%s | action=%s | "
                "priority=%s | confidence=%.2f | reason=%s",
                chat_id,
                decision.action.value,
                decision.priority.value,
                decision.confidence,
                decision.reason,
            )

            # ==========================================================
            # 4. IGNORE
            # ==========================================================

            if not decision.should_respond:
                return AgentRunResult(
                    success=True,
                    decision=decision,
                    should_send=False,
                    metadata={
                        "action": decision.action.value,
                        "ignored": True,
                    },
                )

            # ==========================================================
            # 5. AI RESPONSE
            # ==========================================================

            response_text = ""

            if self._requires_ai_response(decision):
                response_text = await self._generate_response(
                    chat_id=chat_id,
                    user_id=user_id,
                    group_id=group_id,
                    user_text=user_text,
                    reply_to_message_id=reply_to_message_id,
                    runtime_context=runtime_context,
                )

                if not response_text.strip():
                    return AgentRunResult(
                        success=False,
                        decision=decision,
                        should_send=False,
                        error="AI response empty",
                    )

            # ==========================================================
            # 6. PLAN
            # ==========================================================

            plan = await self.planner.create_plan(
                decision=decision,
                user_text=user_text,
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,
                reply_to_message_id=reply_to_message_id,
                response_text=response_text,
            )

            # ==========================================================
            # 7. EXECUTOR
            # ==========================================================

            execution = await self.executor.execute(
                plan
            )

            success = execution.success

            # ==========================================================
            # 8. RESULT
            # ==========================================================

            return AgentRunResult(
                success=success,
                decision=decision,
                plan=plan,
                execution=execution,
                response_text=response_text,
                should_send=success and bool(response_text.strip()),
                metadata={
                    "action": decision.action.value,
                    "priority": decision.priority.value,
                    "confidence": decision.confidence,
                    "plan_id": plan.plan_id,
                },
            )

        except Exception as exc:
            logger.exception(
                "Agent orchestration failed | chat=%s",
                chat_id,
            )

            return AgentRunResult(
                success=False,
                should_send=False,
                error=str(exc),
            )

    # ==================================================================
    # AI RESPONSE
    # ==================================================================

    async def _generate_response(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        group_id: int | None,
        user_text: str,
        reply_to_message_id: int | None,
        runtime_context: AgentRuntimeContext,
    ) -> str:
        """
        Mavjud AI Engine orqali tabiiy javob yaratadi.

        engine.py o'zgartirilmaydi.
        """

        try:
            result = await ai_engine.generate(
                chat_id=chat_id,
                user_id=user_id,
                group_id=group_id,
                user_text=user_text,
                reply_to_message_id=reply_to_message_id,
            )

            if result is None:
                return ""

            # AIResponse dataclass bo'lishi mumkin.
            if hasattr(result, "text"):
                return str(result.text).strip()

            # Ba'zi engine implementatsiyalar string qaytarishi mumkin.
            if isinstance(result, str):
                return result.strip()

            # Dict qaytsa.
            if isinstance(result, dict):
                text = result.get("text")

                if text is None:
                    text = result.get("response")

                if text is not None:
                    return str(text).strip()

            return str(result).strip()

        except Exception:
            logger.exception(
                "AI response generation failed | chat=%s",
                chat_id,
            )

            raise

    # ==================================================================
    # ACTION POLICY
    # ==================================================================

    @staticmethod
    def _requires_ai_response(
        decision: BrainDecision,
    ) -> bool:
        """
        Qaysi Brain action AI matnli javob talab qilishini belgilaydi.
        """

        action = decision.action.value

        return action in {
            "RESPOND",
            "ASK_CLARIFICATION",
            "CONTINUE_CONVERSATION",
            "PROACTIVE_MESSAGE",
        }

    # ==================================================================
    # CONTEXT CONVERSION
    # ==================================================================

    @staticmethod
    def _runtime_to_context(
        runtime_context: AgentRuntimeContext,
    ) -> dict[str, Any]:
        """
        Runtime context'ni Brain tushunadigan dict ko'rinishiga o'tkazadi.
        """

        context: dict[str, Any] = {}

        # Agent context
        if hasattr(runtime_context, "agent_context"):
            context["agent_context"] = (
                runtime_context.agent_context
            )

        # Emotional state
        if hasattr(runtime_context, "emotional_context"):
            context["emotional_context"] = (
                runtime_context.emotional_context
            )

        # Relationship
        if hasattr(runtime_context, "relationship_context"):
            context["relationship_context"] = (
                runtime_context.relationship_context
            )

        # Memory/privacy flags
        for field in (
            "memory_enabled",
            "private_memory_allowed",
            "group_memory_allowed",
        ):
            if hasattr(runtime_context, field):
                context[field] = getattr(
                    runtime_context,
                    field,
                )

        return context

    # ==================================================================
    # STATS
    # ==================================================================

    def stats(self) -> dict[str, Any]:
        return {
            "brain": self.brain.stats()
            if hasattr(self.brain, "stats")
            else {},
            "planner": self.planner.stats()
            if hasattr(self.planner, "stats")
            else {},
            "executor": self.executor.stats()
            if hasattr(self.executor, "stats")
            else {},
        }


sara_orchestrator = SaraOrchestrator()
