from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

from app.config.settings import settings

logger = logging.getLogger("sara.agent.proactive")


# ============================================================
# PROACTIVE DECISION
# ============================================================

@dataclass
class ProactiveDecision:
    should_respond: bool
    reason: str
    confidence: float = 0.0


# ============================================================
# GROUP STATE
# ============================================================

@dataclass
class GroupActivity:
    last_activity: float = 0.0
    last_response: float = 0.0
    message_count: int = 0
    response_count: int = 0


# ============================================================
# PROACTIVE AGENT
# ============================================================

class ProactiveAgent:

    def __init__(self) -> None:

        self._groups: dict[int, GroupActivity] = {}

        # Proactive javob ehtimollari.
        self.question_probability = 0.35
        self.random_probability = 0.04

        # Juda tez-tez gapirmasligi uchun.
        self.minimum_cooldown = max(
            1,
            settings.proactive_cooldown_seconds,
        )

        # Quiet mode'da qancha vaqt o'tgach
        # yana tabiiy ravishda gapirish mumkin.
        self.quiet_interval = max(
            1,
            settings.quiet_group_interval_seconds,
        )

    # ========================================================
    # INTERNAL
    # ========================================================

    def _get_state(
        self,
        chat_id: int,
    ) -> GroupActivity:

        state = self._groups.get(chat_id)

        if state is None:

            state = GroupActivity()

            self._groups[chat_id] = state

        return state

    def _now(self) -> float:
        return time.monotonic()

    # ========================================================
    # ACTIVITY
    # ========================================================

    def record_activity(
        self,
        *,
        chat_id: int,
    ) -> None:

        state = self._get_state(chat_id)

        state.last_activity = self._now()
        state.message_count += 1

    # ========================================================
    # RESPONSE
    # ========================================================

    def record_response(
        self,
        *,
        chat_id: int,
    ) -> None:

        state = self._get_state(chat_id)

        state.last_response = self._now()
        state.response_count += 1

    # ========================================================
    # COOLDOWN
    # ========================================================

    def cooldown_remaining(
        self,
        *,
        chat_id: int,
    ) -> float:

        state = self._get_state(chat_id)

        if state.last_response <= 0:
            return 0.0

        elapsed = (
            self._now()
            - state.last_response
        )

        remaining = (
            self.minimum_cooldown
            - elapsed
        )

        return max(
            0.0,
            remaining,
        )

    def cooldown_ready(
        self,
        *,
        chat_id: int,
    ) -> bool:

        return (
            self.cooldown_remaining(
                chat_id=chat_id
            )
            <= 0
        )

    # ========================================================
    # QUIET INTERVAL
    # ========================================================

    def quiet_interval_passed(
        self,
        *,
        chat_id: int,
    ) -> bool:

        state = self._get_state(chat_id)

        if state.last_response <= 0:
            return True

        elapsed = (
            self._now()
            - state.last_response
        )

        return elapsed >= self.quiet_interval

    # ========================================================
    # QUESTION DETECTION
    # ========================================================

    def question_score(
        self,
        *,
        message_is_question: bool,
        sara_called: bool,
        message_is_reply_to_sara: bool,
    ) -> float:

        score = 0.0

        if message_is_question:
            score += 0.45

        if sara_called:
            score += 0.40

        if message_is_reply_to_sara:
            score += 0.45

        return min(
            1.0,
            score,
        )

    # ========================================================
    # MAIN DECISION ENGINE
    # ========================================================

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

        # ----------------------------------------------------
        # GLOBAL PROACTIVE SYSTEM
        # ----------------------------------------------------

        if not settings.proactive_group_mode:

            return ProactiveDecision(
                should_respond=False,
                reason="global_proactive_disabled",
                confidence=1.0,
            )

        # ----------------------------------------------------
        # GROUP ENABLED
        # ----------------------------------------------------

        if not group_enabled:

            return ProactiveDecision(
                should_respond=False,
                reason="group_disabled",
                confidence=1.0,
            )

        # ----------------------------------------------------
        # BOT → BOT
        # ----------------------------------------------------

        if is_bot_message:

            if not settings.bot_to_bot_mode:

                return ProactiveDecision(
                    should_respond=False,
                    reason="bot_to_bot_disabled",
                    confidence=1.0,
                )

            # Bot xabariga faqat SARA aniq chaqirilgan bo'lsa
            # yoki SARA'ga reply bo'lsa javob beradi.
            #
            # Bu juda muhim:
            #
            # boshqa botlar bilan cheksiz suhbat boshlanib
            # ketishining oldini oladi.

            if not sara_called and not message_is_reply_to_sara:

                return ProactiveDecision(
                    should_respond=False,
                    reason="bot_not_explicitly_addressed",
                    confidence=0.95,
                )

        # ----------------------------------------------------
        # DIRECT CALL
        # ----------------------------------------------------

        if sara_called:

            return ProactiveDecision(
                should_respond=True,
                reason="sara_called",
                confidence=1.0,
            )

        # ----------------------------------------------------
        # REPLY TO SARA
        # ----------------------------------------------------

        if message_is_reply_to_sara:

            return ProactiveDecision(
                should_respond=True,
                reason="reply_to_sara",
                confidence=1.0,
            )

        # ----------------------------------------------------
        # QUIET MODE
        # ----------------------------------------------------

        if quiet_mode:

            # Quiet mode'da SARA faqat to'g'ridan-to'g'ri
            # chaqirilganda yuqoridagi qoidalardan o'tadi.

            return ProactiveDecision(
                should_respond=False,
                reason="quiet_mode",
                confidence=1.0,
            )

        # ----------------------------------------------------
        # COOLDOWN
        # ----------------------------------------------------

        if not self.cooldown_ready(
            chat_id=chat_id
        ):

            return ProactiveDecision(
                should_respond=False,
                reason="cooldown",
                confidence=0.90,
            )

        # ----------------------------------------------------
        # QUESTION
        # ----------------------------------------------------

        if message_is_question:

            probability = (
                self.question_probability
            )

            roll = random.random()

            if roll < probability:

                return ProactiveDecision(
                    should_respond=True,
                    reason="natural_question_opportunity",
                    confidence=0.65,
                )

        # ----------------------------------------------------
        # RANDOM NATURAL INTERVENTION
        # ----------------------------------------------------

        roll = random.random()

        if roll < self.random_probability:

            return ProactiveDecision(
                should_respond=True,
                reason="natural_group_intervention",
                confidence=0.30,
            )

        # ----------------------------------------------------
        # OTHERWISE SILENT
        # ----------------------------------------------------

        return ProactiveDecision(
            should_respond=False,
            reason="no_response_opportunity",
            confidence=0.80,
        )

    # ========================================================
    # GROUP STATISTICS
    # ========================================================

    def get_state(
        self,
        *,
        chat_id: int,
    ) -> GroupActivity:

        return self._get_state(chat_id)

    def get_stats(
        self,
        *,
        chat_id: int,
    ) -> dict[str, int | float]:

        state = self._get_state(chat_id)

        return {
            "message_count": state.message_count,
            "response_count": state.response_count,
            "last_activity": state.last_activity,
            "last_response": state.last_response,
            "cooldown_remaining": self.cooldown_remaining(
                chat_id=chat_id
            ),
        }

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        *,
        chat_id: int,
    ) -> None:

        self._groups.pop(
            chat_id,
            None,
        )

        logger.info(
            "Proactive state reset | chat=%s",
            chat_id,
        )

    # ========================================================
    # CLEANUP
    # ========================================================

    def cleanup(
        self,
        *,
        max_idle_seconds: int = 86400,
    ) -> int:

        now = self._now()

        expired: list[int] = []

        for chat_id, state in self._groups.items():

            last_activity = (
                state.last_activity
                or state.last_response
            )

            if last_activity <= 0:
                continue

            if (
                now - last_activity
                > max_idle_seconds
            ):

                expired.append(
                    chat_id
                )

        for chat_id in expired:

            self._groups.pop(
                chat_id,
                None,
            )

        if expired:

            logger.info(
                "Proactive cleanup: %s ta group state o'chirildi.",
                len(expired),
            )

        return len(expired)


# ============================================================
# GLOBAL INSTANCE
# ============================================================

proactive_agent = ProactiveAgent()
