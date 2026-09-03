from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.ai.memory_extractor import (
    ExtractedMemory,
    extract_memories,
)
from app.memory.manager import memory_manager

logger = logging.getLogger("sara.memory.auto_save")


# ============================================================
# SECURITY
# ============================================================

SECRET_PATTERNS = (
    re.compile(
        r"(?i)(api[_ -]?key|token|password|passwd|secret)"
        r"\s*[:=]\s*\S+"
    ),
    re.compile(
        r"(?i)sk-[a-zA-Z0-9_\-]{10,}"
    ),
    re.compile(
        r"(?i)bot\d{6,}:[a-zA-Z0-9_-]{20,}"
    ),
)


def contains_secret(text: str) -> bool:
    """
    Xabarda API key/token/password kabi sirli
    ma'lumot borligini tekshiradi.
    """

    if not text:
        return False

    return any(
        pattern.search(text)
        for pattern in SECRET_PATTERNS
    )


def sanitize_memory_text(text: str) -> str:
    """
    Memory ichiga secret tushib ketmasligi uchun
    oddiy sanitizatsiya.
    """

    if not text:
        return ""

    result = text.strip()

    for pattern in SECRET_PATTERNS:
        result = pattern.sub(
            "[SECRET_REMOVED]",
            result,
        )

    return result.strip()


# ============================================================
# MEMORY TYPES
# ============================================================

USER_MEMORY_TYPES = {
    "IMPORTANT_FACT",
    "PREFERENCE",
    "PROMISE",
    "PLAN",
    "EVENT",
    "RELATIONSHIP",
    "USER_TRAIT",
    "CONVERSATION_SUMMARY",
}

GROUP_MEMORY_TYPES = {
    "GROUP_FACT",
    "CONVERSATION_SUMMARY",
    "EVENT",
    "PLAN",
}


@dataclass(slots=True)
class AutoSaveResult:
    """
    Memory auto-save natijasi.
    """

    user_saved: int = 0
    group_saved: int = 0
    skipped: int = 0
    secrets_blocked: int = 0
    errors: int = 0


# ============================================================
# DUPLICATE CHECK
# ============================================================

async def _memory_exists(
    *,
    user_id: int | None = None,
    group_id: int | None = None,
    content: str,
) -> bool:
    """
    Bir xil memory qayta-qayta yozilib ketmasligi uchun
    mavjud memorylarni qidiradi.
    """

    try:

        if user_id is not None:

            results = await memory_manager.search_user_memory(
                user_telegram_id=user_id,
                query=content,
                limit=5,
            )

            return bool(results)

        if group_id is not None:

            results = await memory_manager.search_group_memory(
                group_telegram_id=group_id,
                query=content,
                limit=5,
            )

            return bool(results)

    except Exception:

        logger.exception(
            "Memory duplicate check failed."
        )

    return False


# ============================================================
# SAVE USER MEMORY
# ============================================================

async def save_user_extracted_memory(
    *,
    user_id: int,
    extracted: ExtractedMemory,
    source_message_id: int | None = None,
) -> bool:
    """
    ExtractedMemory → UserMemory.
    """

    content = sanitize_memory_text(
        extracted.content
    )

    if not content:
        return False

    if contains_secret(content):

        logger.warning(
            "Secret-like memory blocked | user=%s",
            user_id,
        )

        return False

    memory_type = str(
        extracted.memory_type
    ).upper()

    if memory_type not in USER_MEMORY_TYPES:
        return False

    # Juda past sifatli memoryni saqlamaymiz.
    if extracted.confidence < 0.35:
        return False

    # Duplicate tekshirish.
    if await _memory_exists(
        user_id=user_id,
        content=content,
    ):
        return False

    try:

        await memory_manager.save_user_memory(
            user_telegram_id=user_id,
            memory_type=memory_type,
            content=content,
            importance=max(
                0.0,
                min(
                    1.0,
                    float(extracted.importance),
                ),
            ),
            confidence=max(
                0.0,
                min(
                    1.0,
                    float(extracted.confidence),
                ),
            ),
            source_message_id=source_message_id,
        )

        logger.debug(
            "User memory saved | "
            "user=%s | type=%s | content=%s",
            user_id,
            memory_type,
            content[:120],
        )

        return True

    except Exception:

        logger.exception(
            "User memory save failed | user=%s",
            user_id,
        )

        return False


# ============================================================
# SAVE GROUP MEMORY
# ============================================================

async def save_group_extracted_memory(
    *,
    group_id: int,
    extracted: ExtractedMemory,
    source_message_id: int | None = None,
) -> bool:
    """
    ExtractedMemory → GroupMemory.
    """

    content = sanitize_memory_text(
        extracted.content
    )

    if not content:
        return False

    if contains_secret(content):

        logger.warning(
            "Secret-like group memory blocked | group=%s",
            group_id,
        )

        return False

    memory_type = str(
        extracted.memory_type
    ).upper()

    if memory_type not in GROUP_MEMORY_TYPES:
        return False

    if extracted.confidence < 0.35:
        return False

    if await _memory_exists(
        group_id=group_id,
        content=content,
    ):
        return False

    try:

        await memory_manager.save_group_memory(
            group_telegram_id=group_id,
            memory_type=memory_type,
            content=content,
            importance=max(
                0.0,
                min(
                    1.0,
                    float(extracted.importance),
                ),
            ),
            confidence=max(
                0.0,
                min(
                    1.0,
                    float(extracted.confidence),
                ),
            ),
            source_message_id=source_message_id,
        )

        logger.debug(
            "Group memory saved | "
            "group=%s | type=%s | content=%s",
            group_id,
            memory_type,
            content[:120],
        )

        return True

    except Exception:

        logger.exception(
            "Group memory save failed | group=%s",
            group_id,
        )

        return False


# ============================================================
# MAIN AUTO SAVE
# ============================================================

async def auto_save_memories(
    *,
    text: str,
    user_id: int | None = None,
    group_id: int | None = None,
    source_message_id: int | None = None,
) -> AutoSaveResult:
    """
    Bitta xabarni AI memory extractor orqali tahlil qilib,
    mos memorylarga saqlaydi.

    Conversation history bundan alohida saqlanadi.
    """

    result = AutoSaveResult()

    text = (text or "").strip()

    if not text:
        result.skipped += 1
        return result

    # ========================================================
    # SECURITY
    # ========================================================

    if contains_secret(text):

        logger.warning(
            "Secret-like message detected. "
            "Long-term memory save skipped."
        )

        result.secrets_blocked += 1

        return result

    # ========================================================
    # EXTRACT
    # ========================================================

    try:

        extracted_memories = await extract_memories(
            text=text,
            user_id=user_id,
            group_id=group_id,
        )

    except Exception:

        logger.exception(
            "Memory extraction failed."
        )

        result.errors += 1

        return result

    if not extracted_memories:

        result.skipped += 1
        return result

    # ========================================================
    # SAVE EACH MEMORY
    # ========================================================

    for extracted in extracted_memories:

        if not extracted.content:
            result.skipped += 1
            continue

        saved = False

        # ----------------------------------------------------
        # GROUP MEMORY
        # ----------------------------------------------------

        if (
            group_id is not None
            and str(extracted.memory_type).upper()
            in GROUP_MEMORY_TYPES
        ):

            saved = await save_group_extracted_memory(
                group_id=group_id,
                extracted=extracted,
                source_message_id=source_message_id,
            )

            if saved:
                result.group_saved += 1
                continue

        # ----------------------------------------------------
        # USER MEMORY
        # ----------------------------------------------------

        if (
            user_id is not None
            and str(extracted.memory_type).upper()
            in USER_MEMORY_TYPES
        ):

            saved = await save_user_extracted_memory(
                user_id=user_id,
                extracted=extracted,
                source_message_id=source_message_id,
            )

            if saved:
                result.user_saved += 1
                continue

        # ----------------------------------------------------
        # NOTHING SAVED
        # ----------------------------------------------------

        if not saved:
            result.skipped += 1

    logger.info(
        "Memory auto-save completed | "
        "user=%s | group=%s | user_saved=%s | "
        "group_saved=%s | skipped=%s | blocked=%s",
        user_id,
        group_id,
        result.user_saved,
        result.group_saved,
        result.skipped,
        result.secrets_blocked,
    )

    return result


# ============================================================
# SIMPLE HELPERS
# ============================================================

async def remember_user(
    *,
    user_id: int,
    text: str,
    source_message_id: int | None = None,
) -> bool:
    """
    To'g'ridan-to'g'ri user memory saqlash.
    """

    if not text.strip():
        return False

    if contains_secret(text):
        return False

    try:

        await memory_manager.save_user_memory(
            user_telegram_id=user_id,
            memory_type="IMPORTANT_FACT",
            content=sanitize_memory_text(text),
            importance=0.75,
            confidence=0.90,
            source_message_id=source_message_id,
        )

        return True

    except Exception:

        logger.exception(
            "remember_user failed | user=%s",
            user_id,
        )

        return False


async def remember_group(
    *,
    group_id: int,
    text: str,
    source_message_id: int | None = None,
) -> bool:
    """
    To'g'ridan-to'g'ri group memory saqlash.
    """

    if not text.strip():
        return False

    if contains_secret(text):
        return False

    try:

        await memory_manager.save_group_memory(
            group_telegram_id=group_id,
            memory_type="GROUP_FACT",
            content=sanitize_memory_text(text),
            importance=0.75,
            confidence=0.90,
            source_message_id=source_message_id,
        )

        return True

    except Exception:

        logger.exception(
            "remember_group failed | group=%s",
            group_id,
        )

        return False
