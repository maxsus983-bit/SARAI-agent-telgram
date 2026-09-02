from __future__ import annotations

import random
import time
from dataclasses import dataclass

from app.config.settings import settings


@dataclass
class ProactiveDecision:
    should_respond: bool
    reason: str


class ProactiveAgent:

    def __init__(self) -> None:
        self._last_activity: dict[int, float] = {}
        self._last_response: dict[int, float] = {}

    def _cooldown_passed(
        self,
        *,
        chat_id: int,
    ) -> bool:

        last = self._last_response.get(chat_id)

        if last is None:
            return True

        return (
            time.monotonic() - last
            >= settings.proactive_cooldown_seconds
        )

    def record_activity(
        self,
        *,
        chat_id: int,
    ) -> None:
        self._last_activity[chat_id] = time.monotonic()

    def record_response(
        self,
        *,
        chat_id: int,
    ) -> None:
        self._last_response[chat_id] = time.monotonic()

    def decide(
        self,
        *,
        chat_id: int,
        group_enabled: bool = True,
        quiet_mode: bool = False,
        sara_called: bool = False,
        message_is_question: bool = False,
        message_is_reply_to_sara: bool = False,
    ) -> ProactiveDecision:

        if not settings.proactive_group_mode:
            return ProactiveDecision(
                False,
                "Proactive mode .env orqali o'chirilgan.",
            )

        if not group_enabled:
            return ProactiveDecision(
                False,
                "Guruh proactive mode o'chirilgan.",
            )

        if sara_called:
            return ProactiveDecision(
                True,
                "SARA explicitly chaqirilgan.",
            )

        if message_is_reply_to_sara:
            return ProactiveDecision(
                True,
                "SARA xabariga reply qilindi.",
            )

        if not self._cooldown_passed(
            chat_id=chat_id,
        ):
            return ProactiveDecision(
                False,
                "Proactive cooldown.",
            )

        if quiet_mode:
            return ProactiveDecision(
                False,
                "Quiet mode.",
            )

        if message_is_question:
            # Savol bo'lsa javob berish ehtimoli yuqoriroq.
            if random.random() < 0.35:
                return ProactiveDecision(
                    True,
                    "Savolga proactive javob.",
                )

        # Oddiy suhbatga juda kam aralashadi.
        if random.random() < 0.04:
            return ProactiveDecision(
                True,
                "Low probability proactive response.",
            )

        return ProactiveDecision(
            False,
            "Proactive response kerak emas.",
        )


proactive_agent = ProactiveAgent()
