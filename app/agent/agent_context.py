from __future__ import annotations

import logging

from app.agent.emotional_state import emotional_state
from app.agent.relationship import relationship_manager

logger = logging.getLogger("sara.agent.context")


class AgentContextBuilder:
    """
    SARA Agent uchun qo'shimcha kontekst yaratadi.

    Bu context:
        - session emotional state
        - user relationship
        - group/user interaction holati

    kabi ma'lumotlarni AI'ga tushunarli formatga aylantiradi.
    """

    async def build(
        self,
        *,
        chat_id: int,
        user_id: int,
        relationship_user_id: int | None = None,
    ) -> str:

        sections: list[str] = []

        # ====================================================
        # EMOTIONAL / SESSION STATE
        # ====================================================

        try:
            emotion_context = emotional_state.build_context(
                chat_id=chat_id,
                user_id=user_id,
            )

            if emotion_context:
                sections.append(
                    "SARA SESSION STATE\n"
                    "=================\n"
                    f"{emotion_context}\n\n"
                    "Bu real inson hissiyoti emas. "
                    "Bu faqat SARA javob uslubini "
                    "moslashtirish uchun ishlatiladigan "
                    "session holat."
                )

        except Exception:
            logger.exception(
                "Emotional state context yaratishda xato."
            )

        # ====================================================
        # RELATIONSHIP
        # ====================================================

        if relationship_user_id is not None:

            try:
                relationship_context = (
                    await relationship_manager.build_context(
                        user_a=user_id,
                        user_b=relationship_user_id,
                    )
                )

                if relationship_context:
                    sections.append(
                        "SARA RELATIONSHIP CONTEXT\n"
                        "=========================\n"
                        f"{relationship_context}"
                    )

            except Exception:
                logger.exception(
                    "Relationship context yaratishda xato."
                )

        # ====================================================
        # FINAL
        # ====================================================

        if not sections:
            return (
                "SARA AGENT CONTEXT\n"
                "==================\n"
                "Hozircha qo'shimcha agent context mavjud emas."
            )

        return "\n\n".join(sections)


agent_context_builder = AgentContextBuilder()
