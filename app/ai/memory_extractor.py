from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.ai.openrouter import OpenRouterError, openrouter


logger = logging.getLogger("sara.ai.memory_extractor")


# ============================================================
# MEMORY TYPES
# ============================================================

IMPORTANT_FACT = "IMPORTANT_FACT"
PREFERENCE = "PREFERENCE"
PROMISE = "PROMISE"
PLAN = "PLAN"
EVENT = "EVENT"
RELATIONSHIP = "RELATIONSHIP"
USER_TRAIT = "USER_TRAIT"
GROUP_FACT = "GROUP_FACT"
CONVERSATION_SUMMARY = "CONVERSATION_SUMMARY"


VALID_MEMORY_TYPES = {
    IMPORTANT_FACT,
    PREFERENCE,
    PROMISE,
    PLAN,
    EVENT,
    RELATIONSHIP,
    USER_TRAIT,
    GROUP_FACT,
    CONVERSATION_SUMMARY,
}


# ============================================================
# SECRET DETECTION
# ============================================================

_SECRET_PATTERNS = [
    re.compile(
        r"(?:api[_ -]?key|apikey)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:token|access[_ -]?token)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:password|passwd|parol)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"Bearer\s+[A-Za-z0-9._\-]+",
        re.IGNORECASE,
    ),
    re.compile(
        r"sk-[A-Za-z0-9_\-]+",
        re.IGNORECASE,
    ),
]


def contains_secret(text: str) -> bool:
    """
    Text ichida credential/secret bo'lishi ehtimolini tekshiradi.
    """

    if not text:
        return False

    return any(
        pattern.search(text)
        for pattern in _SECRET_PATTERNS
    )


# ============================================================
# EXTRACTED MEMORY
# ============================================================

@dataclass(slots=True)
class ExtractedMemory:
    memory_type: str
    content: str
    importance: int = 50
    confidence: float = 0.8
    user_telegram_id: int | None = None
    group_telegram_id: int | None = None

    def __post_init__(self) -> None:

        self.memory_type = (
            str(self.memory_type)
            .strip()
            .upper()
        )

        self.content = (
            str(self.content)
            .strip()
        )

        try:
            self.importance = int(
                self.importance
            )
        except (
            TypeError,
            ValueError,
        ):
            self.importance = 50

        self.importance = max(
            0,
            min(self.importance, 100),
        )

        try:
            self.confidence = float(
                self.confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            self.confidence = 0.8

        self.confidence = max(
            0.0,
            min(self.confidence, 1.0),
        )


# ============================================================
# PROMPT
# ============================================================

MEMORY_EXTRACTION_PROMPT = """
You are SARA AI's internal memory extraction module.

Analyze the latest user message and determine whether it
contains information worth remembering for future conversations.

Extract ONLY information that is genuinely useful later.

Possible memory types:

IMPORTANT_FACT
PREFERENCE
PROMISE
PLAN
EVENT
RELATIONSHIP
USER_TRAIT
GROUP_FACT
CONVERSATION_SUMMARY

Do NOT extract:

- casual greetings
- ordinary questions
- random jokes
- temporary statements
- guesses
- assumptions
- API keys
- passwords
- authentication tokens
- access tokens
- bot tokens
- secrets
- credentials

Do not invent information.

The content must be directly supported by the conversation.

Importance:

0-30   = low
31-60  = medium
61-80  = important
81-100 = very important

Confidence:

0.0-1.0

Return ONLY valid JSON.

Format:

[
  {
    "memory_type": "IMPORTANT_FACT",
    "content": "User's name is Ali",
    "importance": 90,
    "confidence": 1.0
  }
]

If there is nothing worth remembering:

[]

Do not write markdown.
Do not write explanations.
Return JSON only.
""".strip()


# ============================================================
# JSON EXTRACTION
# ============================================================

def _extract_json(text: str) -> Any:
    """
    AI ba'zan JSONni ```json ... ``` ichida qaytarishi mumkin.

    Shu wrapperni olib tashlaydi va JSONni topishga harakat qiladi.
    """

    text = str(text or "").strip()

    if not text:
        return []

    # Markdown code block
    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # To'g'ridan-to'g'ri JSON
    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # Birinchi [ va oxirgi ] orasini olish
    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end > start:

        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)

        except json.JSONDecodeError:
            return []

    return []


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_items(
    data: Any,
    *,
    user_id: int | None = None,
    group_id: int | None = None,
) -> list[ExtractedMemory]:

    if not isinstance(data, list):
        return []

    results: list[ExtractedMemory] = []

    for item in data:

        if not isinstance(item, dict):
            continue

        memory_type = str(
            item.get("memory_type", "")
        ).strip().upper()

        content = str(
            item.get("content", "")
        ).strip()

        if not memory_type:
            continue

        if memory_type not in VALID_MEMORY_TYPES:
            continue

        if not content:
            continue

        # Secretni umuman saqlamaymiz.
        if contains_secret(content):
            logger.warning(
                "Secret-like memory rejected."
            )
            continue

        try:
            importance = int(
                item.get(
                    "importance",
                    50,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            importance = 50

        try:
            confidence = float(
                item.get(
                    "confidence",
                    0.8,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = 0.8

        memory = ExtractedMemory(
            memory_type=memory_type,
            content=content,
            importance=importance,
            confidence=confidence,
            user_telegram_id=user_id,
            group_telegram_id=group_id,
        )

        results.append(memory)

    return results


# ============================================================
# EXTRACTOR
# ============================================================

class MemoryExtractor:

    async def extract(
        self,
        user_message: str,
        conversation_context: str = "",
        *,
        user_id: int | None = None,
        group_id: int | None = None,
    ) -> list[ExtractedMemory]:

        user_message = str(
            user_message or ""
        ).strip()

        if not user_message:
            return []

        # Agar xabarning o'zi secretga o'xshasa,
        # memory extractionni umuman bajarmaymiz.
        if contains_secret(user_message):

            logger.info(
                "Memory extraction skipped: "
                "secret-like message."
            )

            return []

        context = str(
            conversation_context or ""
        )

        # Contextni cheklaymiz.
        if len(context) > 6000:
            context = context[-6000:]

        prompt = f"""
RECENT CONVERSATION:

{context}

LATEST USER MESSAGE:

{user_message}

Determine whether the latest message contains
information worth remembering.
Return JSON only.
""".strip()

        try:

            response = await openrouter.chat(
                messages=[
                    {
                        "role": "system",
                        "content": MEMORY_EXTRACTION_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.1,
            )

        except OpenRouterError as exc:

            logger.warning(
                "Memory extraction OpenRouter error: %s",
                exc,
            )

            return []

        except Exception as exc:

            logger.exception(
                "Unexpected memory extraction error: %s",
                exc,
            )

            return []

        raw_text = response.text.strip()

        data = _extract_json(raw_text)

        memories = _normalize_items(
            data,
            user_id=user_id,
            group_id=group_id,
        )

        logger.debug(
            "Memory extraction completed: %s memories.",
            len(memories),
        )

        return memories


# ============================================================
# COMPATIBILITY HELPERS
# ============================================================

async def extract_memories(
    text: str,
    *,
    user_id: int | None = None,
    group_id: int | None = None,
    conversation_context: str = "",
) -> list[ExtractedMemory]:

    return await memory_extractor.extract(
        user_message=text,
        conversation_context=conversation_context,
        user_id=user_id,
        group_id=group_id,
    )


async def extract_user_memories(
    text: str,
    user_id: int,
    conversation_context: str = "",
) -> list[ExtractedMemory]:

    memories = await memory_extractor.extract(
        user_message=text,
        conversation_context=conversation_context,
        user_id=user_id,
        group_id=None,
    )

    # User memoryga group-only memory tushmasligi uchun.
    return [
        memory
        for memory in memories
        if memory.memory_type != GROUP_FACT
    ]


async def extract_group_memories(
    text: str,
    group_id: int,
    conversation_context: str = "",
) -> list[ExtractedMemory]:

    memories = await memory_extractor.extract(
        user_message=text,
        conversation_context=conversation_context,
        user_id=None,
        group_id=group_id,
    )

    return [
        memory
        for memory in memories
        if memory.memory_type == GROUP_FACT
        or memory.memory_type
        in {
            CONVERSATION_SUMMARY,
            EVENT,
            PLAN,
        }
    ]


memory_extractor = MemoryExtractor()


__all__ = [
    "ExtractedMemory",
    "MemoryExtractor",
    "memory_extractor",
    "extract_memories",
    "extract_user_memories",
    "extract_group_memories",
    "contains_secret",
    "IMPORTANT_FACT",
    "PREFERENCE",
    "PROMISE",
    "PLAN",
    "EVENT",
    "RELATIONSHIP",
    "USER_TRAIT",
    "GROUP_FACT",
    "CONVERSATION_SUMMARY",
  ]
