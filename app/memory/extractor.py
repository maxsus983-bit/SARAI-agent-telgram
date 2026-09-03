from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.ai.openrouter import openrouter_client

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
# SECURITY
# ============================================================

SECRET_PATTERNS = (
    re.compile(
        r"(?i)(api[_ -]?key|token|password|passwd|secret)"
        r"\s*[:=]\s*\S+"
    ),
    re.compile(
        r"(?i)\bsk-[a-zA-Z0-9_-]{10,}\b"
    ),
    re.compile(
        r"(?i)\bbot\d{6,}:[a-zA-Z0-9_-]{20,}\b"
    ),
)


def contains_secret(text: str) -> bool:
    if not text:
        return False

    return any(
        pattern.search(text)
        for pattern in SECRET_PATTERNS
    )


def sanitize_text(text: str) -> str:
    """
    Secretlarni memorydan olib tashlaydi.
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
# DATACLASS
# ============================================================

@dataclass(slots=True)
class ExtractedMemory:
    memory_type: str
    content: str
    importance: float = 0.5
    confidence: float = 0.8

    def normalized(self) -> "ExtractedMemory":

        memory_type = (
            str(self.memory_type)
            .strip()
            .upper()
        )

        if memory_type not in VALID_MEMORY_TYPES:
            memory_type = IMPORTANT_FACT

        content = sanitize_text(
            str(self.content).strip()
        )

        importance = max(
            0.0,
            min(
                1.0,
                float(self.importance),
            ),
        )

        confidence = max(
            0.0,
            min(
                1.0,
                float(self.confidence),
            ),
        )

        return ExtractedMemory(
            memory_type=memory_type,
            content=content,
            importance=importance,
            confidence=confidence,
        )


# ============================================================
# SYSTEM PROMPT
# ============================================================

MEMORY_EXTRACTION_PROMPT = """
You are SARA AI's long-term memory extraction system.

Your task:
Analyze the user's message and extract information that may
be useful in future conversations.

IMPORTANT:
Do NOT invent information.
Only extract facts that are actually supported by the message.

Try to remember useful information such as:

- personal facts
- location
- work
- study
- hobbies
- interests
- preferences
- dislikes
- plans
- goals
- promises
- important events
- relationships
- recurring habits
- personality traits
- important conversation facts
- group facts
- ongoing situations

A single message can produce MULTIPLE memories.

Examples:

"Men Toshkentda yashayman va Minecraft o'ynashni yaxshi ko'raman."

Possible memories:

IMPORTANT_FACT:
"User Toshkentda yashaydi."

PREFERENCE:
"User Minecraft o'ynashni yaxshi ko'radi."

Another example:

"Bugun yangi ish topdim."

EVENT:
"User yangi ish topgan."

Another:

"Ertaga serverni ishga tushiraman."

PLAN:
"User ertaga serverni ishga tushirishni rejalashtirgan."

Another:

"Men achchiq ovqatni yoqtirmayman."

PREFERENCE:
"User achchiq ovqatni yoqtirmaydi."

Another:

"Ali mening akam."

RELATIONSHIP:
"Ali userning akasi."

Do NOT store:
- API keys
- passwords
- access tokens
- private authentication secrets
- random meaningless chatter
- information that is not supported by the message

Return ONLY valid JSON.

Format:

{
  "memories": [
    {
      "memory_type": "IMPORTANT_FACT",
      "content": "...",
      "importance": 0.0,
      "confidence": 0.0
    }
  ]
}

Valid memory types:

IMPORTANT_FACT
PREFERENCE
PROMISE
PLAN
EVENT
RELATIONSHIP
USER_TRAIT
GROUP_FACT
CONVERSATION_SUMMARY

importance:
0.0 = almost irrelevant
1.0 = extremely important

confidence:
0.0 = uncertain
1.0 = directly stated

If there is nothing useful to remember:

{
  "memories": []
}
"""


# ============================================================
# JSON EXTRACTION
# ============================================================

def _extract_json(text: str) -> dict[str, Any] | None:
    """
    AI ba'zan JSON oldidan/ketidan markdown yozishi mumkin.
    Shu sabab JSONni ehtiyotkorlik bilan ajratamiz.
    """

    if not text:
        return None

    text = text.strip()

    # ```json ... ```
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    try:
        data = json.loads(text)

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:
        pass

    # Birinchi { va oxirgi } orasini qidiramiz.
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:

        data = json.loads(
            text[start:end + 1]
        )

        if isinstance(data, dict):
            return data

    except json.JSONDecodeError:

        logger.debug(
            "Memory extractor JSON parse failed."
        )

    return None


# ============================================================
# NORMALIZE
# ============================================================

def _normalize_memory(
    raw: Any,
) -> ExtractedMemory | None:

    if not isinstance(raw, dict):
        return None

    memory_type = str(
        raw.get(
            "memory_type",
            IMPORTANT_FACT,
        )
    ).strip().upper()

    content = str(
        raw.get(
            "content",
            "",
        )
    ).strip()

    if not content:
        return None

    if memory_type not in VALID_MEMORY_TYPES:
        memory_type = IMPORTANT_FACT

    try:

        importance = float(
            raw.get(
                "importance",
                0.5,
            )
        )

    except (TypeError, ValueError):

        importance = 0.5

    try:

        confidence = float(
            raw.get(
                "confidence",
                0.8,
            )
        )

    except (TypeError, ValueError):

        confidence = 0.8

    memory = ExtractedMemory(
        memory_type=memory_type,
        content=content,
        importance=importance,
        confidence=confidence,
    ).normalized()

    if not memory.content:
        return None

    # Secret aniqlansa memoryni umuman olmaymiz.
    if contains_secret(memory.content):
        return None

    return memory


# ============================================================
# DEDUPLICATION
# ============================================================

def _deduplicate(
    memories: list[ExtractedMemory],
) -> list[ExtractedMemory]:

    result: list[ExtractedMemory] = []
    seen: set[tuple[str, str]] = set()

    for memory in memories:

        key = (
            memory.memory_type,
            re.sub(
                r"\s+",
                " ",
                memory.content.lower(),
            ).strip(),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(memory)

    return result


# ============================================================
# MAIN EXTRACTION
# ============================================================

async def extract_memories(
    *,
    text: str,
    user_id: int | None = None,
    group_id: int | None = None,
) -> list[ExtractedMemory]:
    """
    Bitta Telegram xabaridan uzoq muddatli memorylarni chiqaradi.
    """

    text = (text or "").strip()

    if not text:
        return []

    # Secret bo'lsa AI'ga memory extraction uchun yubormaymiz.
    if contains_secret(text):

        logger.warning(
            "Secret-like text blocked from memory extraction."
        )

        return []

    # Juda qisqa/random xabarlarni AI'ga yubormaslik.
    if len(text) < 3:
        return []

    # ========================================================
    # CONTEXT
    # ========================================================

    context_note = ""

    if group_id is not None:

        context_note = """
This message came from a Telegram group.

You may extract:
- facts about the user
- facts about the group
- events
- plans
- relationships
- conversation facts

Use GROUP_FACT only for information specifically about
the group/community.
"""

    elif user_id is not None:

        context_note = """
This message came from a private conversation with the user.
Focus primarily on information about the user.
"""

    # ========================================================
    # USER PROMPT
    # ========================================================

    user_prompt = f"""
Analyze this Telegram message for long-term memory.

{context_note}

MESSAGE:
{text}

Return ONLY JSON.
"""

    try:

        response = await openrouter_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": MEMORY_EXTRACTION_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.1,
        )

    except Exception:

        logger.exception(
            "OpenRouter memory extraction failed."
        )

        return []

    # ========================================================
    # RESPONSE TEXT
    # ========================================================

    if isinstance(response, str):

        response_text = response

    elif isinstance(response, dict):

        response_text = (
            response.get("content")
            or response.get("text")
            or ""
        )

    else:

        response_text = str(response)

    response_text = response_text.strip()

    if not response_text:
        return []

    # ========================================================
    # PARSE JSON
    # ========================================================

    data = _extract_json(
        response_text
    )

    if not data:
        return []

    raw_memories = data.get(
        "memories",
        [],
    )

    if not isinstance(
        raw_memories,
        list,
    ):
        return []

    memories: list[ExtractedMemory] = []

    # ========================================================
    # NORMALIZE EACH MEMORY
    # ========================================================

    for raw in raw_memories:

        memory = _normalize_memory(
            raw
        )

        if memory is None:
            continue

        # Juda past confidence.
        if memory.confidence < 0.25:
            continue

        memories.append(
            memory
        )

    # ========================================================
    # DEDUPLICATE
    # ========================================================

    memories = _deduplicate(
        memories
    )

    # ========================================================
    # LIMIT
    # ========================================================
    #
    # Bitta xabardan haddan tashqari ko'p memory
    # chiqarib yubormaslik.
    #

    memories = memories[:10]

    logger.debug(
        "Memories extracted | user=%s | group=%s | count=%s",
        user_id,
        group_id,
        len(memories),
    )

    return memories


# ============================================================
# CONVENIENCE
# ============================================================

async def extract_user_memories(
    text: str,
    user_id: int | None = None,
) -> list[ExtractedMemory]:

    return await extract_memories(
        text=text,
        user_id=user_id,
        group_id=None,
    )


async def extract_group_memories(
    text: str,
    group_id: int | None = None,
    user_id: int | None = None,
) -> list[ExtractedMemory]:

    return await extract_memories(
        text=text,
        user_id=user_id,
        group_id=group_id,
    )


__all__ = [
    "ExtractedMemory",
    "extract_memories",
    "extract_user_memories",
    "extract_group_memories",
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
