from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class EmotionalState:
    mood: str = "neutral"
    intensity: float = 0.0
    energy: float = 0.5
    curiosity: float = 0.5
    friendliness: float = 0.75
    updated_at: float = 0.0


class EmotionalStateManager:

    def __init__(self) -> None:
        self._states: dict[str, EmotionalState] = {}

    def _key(
        self,
        *,
        chat_id: int,
        user_id: int | None = None,
    ) -> str:
        if user_id is None:
            return f"chat:{chat_id}"

        return f"chat:{chat_id}:user:{user_id}"

    def get(
        self,
        *,
        chat_id: int,
        user_id: int | None = None,
    ) -> EmotionalState:

        key = self._key(
            chat_id=chat_id,
            user_id=user_id,
        )

        state = self._states.get(key)

        if state is None:
            state = EmotionalState(
                updated_at=time.monotonic()
            )

            self._states[key] = state

        self._decay(state)

        return state

    def _decay(
        self,
        state: EmotionalState,
    ) -> None:

        now = time.monotonic()

        if state.updated_at <= 0:
            state.updated_at = now
            return

        elapsed = now - state.updated_at

        if elapsed < 60:
            return

        # Vaqt o'tishi bilan intensity neytral holatga qaytadi.
        decay = min(
            1.0,
            elapsed / 3600,
        )

        state.intensity *= 1.0 - (0.5 * decay)

        state.energy += (
            0.5 - state.energy
        ) * 0.1 * decay

        state.curiosity += (
            0.5 - state.curiosity
        ) * 0.1 * decay

        state.updated_at = now

    def update(
        self,
        *,
        chat_id: int,
        user_id: int | None = None,
        mood: str | None = None,
        intensity_change: float = 0.0,
        energy_change: float = 0.0,
        curiosity_change: float = 0.0,
    ) -> EmotionalState:

        state = self.get(
            chat_id=chat_id,
            user_id=user_id,
        )

        if mood:
            state.mood = mood

        state.intensity = max(
            0.0,
            min(
                1.0,
                state.intensity + intensity_change,
            ),
        )

        state.energy = max(
            0.0,
            min(
                1.0,
                state.energy + energy_change,
            ),
        )

        state.curiosity = max(
            0.0,
            min(
                1.0,
                state.curiosity + curiosity_change,
            ),
        )

        state.updated_at = time.monotonic()

        return state

    def build_context(
        self,
        *,
        chat_id: int,
        user_id: int | None = None,
    ) -> str:

        state = self.get(
            chat_id=chat_id,
            user_id=user_id,
        )

        return (
            f"Mood: {state.mood}\n"
            f"Intensity: {state.intensity:.2f}\n"
            f"Energy: {state.energy:.2f}\n"
            f"Curiosity: {state.curiosity:.2f}\n"
            f"Friendliness: {state.friendliness:.2f}"
        )

    def reset(
        self,
        *,
        chat_id: int,
        user_id: int | None = None,
    ) -> None:

        key = self._key(
            chat_id=chat_id,
            user_id=user_id,
        )

        self._states.pop(key, None)


emotional_state = EmotionalStateManager()
