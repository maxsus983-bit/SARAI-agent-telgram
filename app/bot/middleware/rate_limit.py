from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """
    User va group uchun oddiy in-memory rate limiter.

    Bu Telegram handlerga yetib kelgan xabarlar orasidagi
    minimal vaqtni nazorat qiladi.
    """

    def __init__(self) -> None:
        self._users: dict[int, float] = {}
        self._groups: dict[int, float] = {}

    def allow_user(
        self,
        *,
        user_id: int,
        interval: float,
    ) -> bool:

        now = time.monotonic()

        last = self._users.get(user_id)

        if last is not None:
            if now - last < interval:
                return False

        self._users[user_id] = now

        return True

    def allow_group(
        self,
        *,
        chat_id: int,
        interval: float,
    ) -> bool:

        now = time.monotonic()

        last = self._groups.get(chat_id)

        if last is not None:
            if now - last < interval:
                return False

        self._groups[chat_id] = now

        return True

    def reset_user(
        self,
        *,
        user_id: int,
    ) -> None:

        self._users.pop(
            user_id,
            None,
        )

    def reset_group(
        self,
        *,
        chat_id: int,
    ) -> None:

        self._groups.pop(
            chat_id,
            None,
        )

    def cleanup(
        self,
        *,
        max_age: float = 3600,
    ) -> None:

        now = time.monotonic()

        old_users = [
            user_id
            for user_id, timestamp
            in self._users.items()
            if now - timestamp > max_age
        ]

        for user_id in old_users:
            self._users.pop(
                user_id,
                None,
            )

        old_groups = [
            chat_id
            for chat_id, timestamp
            in self._groups.items()
            if now - timestamp > max_age
        ]

        for chat_id in old_groups:
            self._groups.pop(
                chat_id,
                None,
            )


rate_limiter = RateLimiter()
