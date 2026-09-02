from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class ChainState:
    started_at: float
    last_activity: float
    length: int = 0


class LoopGuard:
    def __init__(
        self,
        *,
        max_chain: int = 5,
        cooldown_seconds: int = 30,
        chain_timeout: int = 300,
    ) -> None:
        self.max_chain = max_chain
        self.cooldown_seconds = cooldown_seconds
        self.chain_timeout = chain_timeout

        self._chains: dict[int, ChainState] = {}
        self._recent_bot_messages: dict[
            int, deque[float]
        ] = defaultdict(lambda: deque(maxlen=20))

        self._last_response: dict[int, float] = {}

    def _cleanup(self) -> None:
        now = time.monotonic()

        expired = [
            chat_id
            for chat_id, state in self._chains.items()
            if now - state.last_activity > self.chain_timeout
        ]

        for chat_id in expired:
            self._chains.pop(chat_id, None)

    def can_respond(
        self,
        *,
        chat_id: int,
        is_bot_message: bool = False,
    ) -> bool:
        self._cleanup()

        now = time.monotonic()

        last_response = self._last_response.get(chat_id)

        if last_response is not None:
            if now - last_response < self.cooldown_seconds:
                return False

        state = self._chains.get(chat_id)

        if state and state.length >= self.max_chain:
            return False

        if is_bot_message:
            recent = self._recent_bot_messages[chat_id]

            while recent and now - recent[0] > self.chain_timeout:
                recent.popleft()

            if len(recent) >= self.max_chain:
                return False

        return True

    def register_bot_message(
        self,
        *,
        chat_id: int,
    ) -> None:
        now = time.monotonic()

        self._recent_bot_messages[chat_id].append(now)

        state = self._chains.get(chat_id)

        if state is None:
            self._chains[chat_id] = ChainState(
                started_at=now,
                last_activity=now,
                length=1,
            )
        else:
            state.last_activity = now
            state.length += 1

    def register_user_message(
        self,
        *,
        chat_id: int,
    ) -> None:
        state = self._chains.get(chat_id)

        if state:
            state.last_activity = time.monotonic()

            # User qayta gapirsa bot-to-bot chain uziladi.
            state.length = 0

    def register_response(
        self,
        *,
        chat_id: int,
    ) -> None:
        self._last_response[chat_id] = time.monotonic()

    def reset(
        self,
        *,
        chat_id: int,
    ) -> None:
        self._chains.pop(chat_id, None)
        self._recent_bot_messages.pop(chat_id, None)
        self._last_response.pop(chat_id, None)

    def chain_length(
        self,
        *,
        chat_id: int,
    ) -> int:
        state = self._chains.get(chat_id)

        if state is None:
            return 0

        return state.length


loop_guard = LoopGuard()
