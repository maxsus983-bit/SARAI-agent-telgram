from __future__ import annotations

from app.agent.emotional_state import emotional_state
from app.agent.relationship import relationship_manager


async def build_agent_context(
    *,
    chat_id: int,
    user_id: int,
) -> str:
    """
    SARA agent holatini AI uchun oddiy text contextga aylantiradi.
    """

    emotion = emotional_state.build_context(
        chat_id=chat_id,
        user_id=user_id,
    )

    return (
        "SARA SESSION STATE\n"
        "=================\n"
        f"{emotion}\n\n"
        "Bu holat real inson hissiyoti emas. "
        "Faqat javob uslubini moslashtirish uchun "
        "session state hisoblanadi."
    )


async def build_relationship_context(
    *,
    user_a: int,
    user_b: int,
) -> str:
    return await relationship_manager.build_context(
        user_a=user_a,
        user_b=user_b,
    )
