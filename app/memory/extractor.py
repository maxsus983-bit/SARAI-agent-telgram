from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExtractedMemory:
    memory_type: str
    content: str
    importance: int = 50
    confidence: float = 1.0


VALID_MEMORY_TYPES = {
    "IMPORTANT_FACT",
    "PREFERENCE",
    "PROMISE",
    "PLAN",
    "EVENT",
    "RELATIONSHIP",
    "USER_TRAIT",
    "GROUP_FACT",
    "CONVERSATION_SUMMARY",
}


def parse_memory_items(data: Any) -> list[ExtractedMemory]:

    if not isinstance(data, list):
        return []

    memories: list[ExtractedMemory] = []

    for item in data:

        if not isinstance(item, dict):
            continue

        memory_type = str(
            item.get(
                "memory_type",
                "IMPORTANT_FACT",
            )
        ).upper()

        content = str(
            item.get("content", "")
        ).strip()

        if not content:
            continue

        if memory_type not in VALID_MEMORY_TYPES:
            memory_type = "IMPORTANT_FACT"

        try:
            importance = int(
                item.get("importance", 50)
            )
        except (TypeError, ValueError):
            importance = 50

        try:
            confidence = float(
                item.get("confidence", 1.0)
            )
        except (TypeError, ValueError):
            confidence = 1.0

        importance = max(
            0,
            min(100, importance),
        )

        confidence = max(
            0.0,
            min(1.0, confidence),
        )

        memories.append(
            ExtractedMemory(
                memory_type=memory_type,
                content=content,
                importance=importance,
                confidence=confidence,
            )
        )

    return memories
