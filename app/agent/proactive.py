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
    """
    SARA guruhlarda proactive javoblarini boshqaradi.

    Maqsad:
    - Har bir xabarga javob bermaslik
    - Cooldown saqlash
    - Quiet group rejimini hurmat qilish
    - Savollarga javob berish ehtimolini oshirish
    - SARA chaqirilganda doim javob berish
    - SARA'ning o'zi ketma-ket xabar yuborib spam qilmasligi
    """

    def __init__(self) -> None:
        self._last_activity: dict[int, float] = {}
        self._last_response: dict[int, float] = {}

    # =========================================================
    # ACTIVITY
    # =========================================================

    def record_activity(
        self,
        *,
        chat_id: int,
    ) -> None:
        self._last_activity[chat_id] = (
            time.monotonic()
        )

    # =========================================================
    # RESPONSE
    # =========================================================

    def record_response(
        self,
        *,
        chat_id: int,
    ) -> None:
        self._last_response[chat_id] = (
            time.monotonic()
        )

    # =========================================================
    # COOLDOWN
    # =========================================================

    def cooldown_passed(
        self,
        *,
        chat_id: int,
    ) -> bool:

        last_response = self._last_response.get(
            chat_id
        )

        if last_response is None:
            return True

        elapsed = (
            time.monotonic()
            - last_response
        )

        return (
            elapsed
            >= settings.proactive_cooldown_seconds
        )

    # =========================================================
    # QUIET CHECK
    # =========================================================

    def should_stay_quiet(
        self,
        *,
        chat_id: int,
    ) -> bool:

        last_response = self._last_response.get(
            chat_id
        )

        if last_response is None:
            return False

        elapsed = (
            time.monotonic()
            - last_response
        )

        return (
            elapsed
            < settings.quiet_group_interval_seconds
        )

    # =========================================================
    # QUESTION DETECTION
    # =========================================================

    @staticmethod
    def looks_like_question(
        text: str,
    ) -> bool:

        if not text:
            return False

        text = text.strip()

        if "?" in text:
            return True

        question_words = (
            "nima",
            "nega",
            "qanday",
            "qachon",
            "qayer",
            "qayerda",
            "kim",
            "kimga",
            "kimni",
            "qancha",
            "qaysi",
            "mumkinmi",
            "bilasanmi",
            "ayt",
            "aytchi",
            "what",
            "why",
            "how",
            "when",
            "where",
            "who",
            "which",
            "can you",
            "do you",
            "почему",
            "как",
            "когда",
            "где",
            "кто",
            "какой",
            "можешь",
        )

        lowered = text.lower()

        return any(
            lowered == word
            or lowered.startswith(word + " ")
            for word in question_words
        )

    # =========================================================
    # DECISION ENGINE
    # =========================================================

    def decide(
        self,
        *,
        chat_id: int,
        group_enabled: bool = True,
        quiet_mode: bool = False,
        sara_called: bool = False,
        message_is_question: bool = False,
        message_is_reply_to_sara: bool = False,
        is_bot_message: bool = False,
    ) -> ProactiveDecision:

        # -----------------------------------------------------
        # GLOBAL SETTING
        # -----------------------------------------------------

        if not settings.proactive_group_mode:
            return ProactiveDecision(
                should_respond=False,
                reason=(
                    "Proactive mode .env orqali "
                    "o'chirilgan."
                ),
            )

        # -----------------------------------------------------
        # GROUP ENABLED
        # -----------------------------------------------------

        if not group_enabled:
            return ProactiveDecision(
                should_respond=False,
                reason=(
                    "Bu guruhda AI faol emas."
                ),
            )

        # -----------------------------------------------------
        # BOT MESSAGE
        # -----------------------------------------------------

        if is_bot_message:
            if not settings.bot_to_bot_mode:
                return ProactiveDecision(
                    should_respond=False,
                    reason=(
                        "Bot-to-bot mode o'chirilgan."
                    ),
                )

        # -----------------------------------------------------
        # EXPLICIT SARA CALL
        # -----------------------------------------------------

        if sara_called:
            return ProactiveDecision(
                should_respond=True,
                reason=(
                    "SARA explicitly chaqirilgan."
                ),
            )

        # -----------------------------------------------------
        # REPLY TO SARA
        # -----------------------------------------------------

        if message_is_reply_to_sara:
            return ProactiveDecision(
                should_respond=True,
                reason=(
                    "SARA xabariga reply qilindi."
                ),
            )

        # -----------------------------------------------------
        # QUIET MODE
        # -----------------------------------------------------

        if quiet_mode:
            return ProactiveDecision(
                should_respond=False,
                reason="Group quiet mode.",
            )

        # -----------------------------------------------------
        # LONG QUIET PERIOD
        # -----------------------------------------------------

        if self.should_stay_quiet(
            chat_id=chat_id
        ):
            return ProactiveDecision(
                should_respond=False,
                reason=(
                    "SARA yaqinda javob berdi."
                ),
            )

        # -----------------------------------------------------
        # COOLDOWN
        # -----------------------------------------------------

        if not self.cooldown_passed(
            chat_id=chat_id
        ):
            return ProactiveDecision(
                should_respond=False,
                reason=(
                    "Proactive cooldown hali tugamagan."
                ),
            )

        # -----------------------------------------------------
        # QUESTION
        # -----------------------------------------------------

        if message_is_question:

            # Savolga javob berish ehtimoli yuqori.
            if random.random() < 0.35:
                return ProactiveDecision(
                    should_respond=True,
                    reason=(
                        "Savolga proactive javob."
                    ),
                )

            return ProactiveDecision(
                should_respond=False,
                reason=(
                    "Savol bo'lsa ham proactive "
                    "javob ehtimoliga tushmadi."
                ),
            )

        # -----------------------------------------------------
        # NORMAL GROUP CHAT
        # -----------------------------------------------------

        # Oddiy suhbatga juda kam aralashadi.
        if random.random() < 0.04:
            return ProactiveDecision(
                should_respond=True,
                reason=(
                    "Tasodifiy natural proactive "
                    "interaction."
                ),
            )

        return ProactiveDecision(
            should_respond=False,
            reason=(
                "Oddiy xabarga proactive javob "
                "kerak emas."
            ),
        )

    # =========================================================
    # GROUP STATE
    # =========================================================

    def get_last_activity(
        self,
        *,
        chat_id: int,
    ) -> float | None:

        return self._last_activity.get(
            chat_id
        )

    def get_last_response(
        self,
        *,
        chat_id: int,
    ) -> float | None:

        return self._last_response.get(
            chat_id
        )

    # =========================================================
    # RESET
    # =========================================================

    def reset(
        self,
        *,
        chat_id: int,
    ) -> None:

        self._last_activity.pop(
            chat_id,
            None,
        )

        self._last_response.pop(
            chat_id,
            None,
        )


proactive_agent = ProactiveAgent()
