from __future__ import annotations

import re


class PrivacyService:

    PRIVATE_MEMORY_MARKER = (
        "PRIVATE USER MEMORY HIDDEN IN GROUP CONTEXT."
    )

    SECRET_PATTERNS = [
        re.compile(
            r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{10,}\b"
        ),
        re.compile(
            r"\b(?:api[_-]?key|token|secret)"
            r"\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:password|parol|пароль)"
            r"\s*[:=]\s*\S+",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b\d{16}\b"
        ),
    ]

    PRIVATE_MARKERS = [
        "private",
        "maxfiy",
        "sir",
        "secret",
        "shaxsiy",
        "личное",
        "секрет",
        "private memory",
    ]

    def is_private_context(
        self,
        *,
        group_id: int | None,
    ) -> bool:

        return group_id is None

    def sanitize_for_group(
        self,
        text: str,
    ) -> str:

        if not text:
            return ""

        result = text

        for pattern in self.SECRET_PATTERNS:
            result = pattern.sub(
                "[REDACTED]",
                result,
            )

        return result

    def is_sensitive_request(
        self,
        text: str,
    ) -> bool:

        if not text:
            return False

        lowered = text.lower()

        return any(
            marker in lowered
            for marker in self.PRIVATE_MARKERS
        )

    def group_memory_allowed(
        self,
        *,
        memory_type: str,
    ) -> bool:

        return memory_type.upper() in {
            "GROUP_FACT",
            "CONVERSATION_SUMMARY",
        }

    def user_memory_allowed_in_private(
        self,
        *,
        memory_type: str,
    ) -> bool:

        return bool(memory_type)

    def can_share_user_memory_to_group(
        self,
        *,
        explicit_confirmation: bool = False,
    ) -> bool:

        # Private memory faqat foydalanuvchi
        # aniq ruxsat berganda ulashilishi mumkin.
        return explicit_confirmation


privacy_service = PrivacyService()
