from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.memory.manager import memory_manager


logger_name = "sara.memory.retrieval"


# ==============================================================
# RESULT MODEL
# ==============================================================


@dataclass(slots=True)
class MemorySearchResult:
    memory: Any
    score: float
    source: str

    @property
    def content(self) -> str:
        return str(getattr(self.memory, "content", ""))

    @property
    def memory_type(self) -> str:
        return str(
            getattr(
                self.memory,
                "memory_type",
                "IMPORTANT_FACT",
            )
        )


# ==============================================================
# TEXT HELPERS
# ==============================================================


def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = str(text).lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def tokenize(text: str) -> set[str]:
    text = normalize_text(text)

    if not text:
        return set()

    words = re.findall(
        r"[a-zA-Zа-яА-ЯёЁўқғҳҚҒҲЎ0-9]+",
        text,
        flags=re.UNICODE,
    )

    # Juda kichik/foydasiz tokenlarni tashlaymiz.
    stop_words = {
        "va",
        "ham",
        "bu",
        "shu",
        "men",
        "sen",
        "u",
        "biz",
        "siz",
        "ular",
        "the",
        "a",
        "an",
        "is",
        "are",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "что",
        "это",
        "и",
        "я",
        "ты",
        "он",
        "она",
    }

    return {
        word
        for word in words
        if len(word) >= 2 and word not in stop_words
    }


# ==============================================================
# SCORING
# ==============================================================


def calculate_relevance(
    *,
    query: str,
    content: str,
    importance: int = 50,
    confidence: float = 1.0,
    memory_type: str = "",
    updated_at: datetime | None = None,
) -> float:
    """
    Memory relevance score.

    Natija taxminan 0..100 oralig‘ida.
    """

    query_normalized = normalize_text(query)
    content_normalized = normalize_text(content)

    if not query_normalized or not content_normalized:
        return 0.0

    query_tokens = tokenize(query_normalized)
    content_tokens = tokenize(content_normalized)

    if not query_tokens:
        return 0.0

    # ----------------------------------------------------------
    # 1. Token overlap
    # ----------------------------------------------------------

    overlap = query_tokens.intersection(content_tokens)

    if overlap:
        overlap_score = (
            len(overlap) / max(len(query_tokens), 1)
        ) * 45.0
    else:
        overlap_score = 0.0

    # ----------------------------------------------------------
    # 2. Exact phrase bonus
    # ----------------------------------------------------------

    phrase_bonus = 0.0

    if query_normalized in content_normalized:
        phrase_bonus = 25.0

    # ----------------------------------------------------------
    # 3. Individual word presence
    # ----------------------------------------------------------

    presence_count = sum(
        1
        for token in query_tokens
        if token in content_normalized
    )

    presence_score = (
        min(
            presence_count / max(len(query_tokens), 1),
            1.0,
        )
        * 10.0
    )

    # ----------------------------------------------------------
    # 4. Importance
    # ----------------------------------------------------------

    safe_importance = max(
        0,
        min(
            int(importance),
            100,
        ),
    )

    importance_score = (
        safe_importance / 100.0
    ) * 10.0

    # ----------------------------------------------------------
    # 5. Confidence
    # ----------------------------------------------------------

    safe_confidence = max(
        0.0,
        min(
            float(confidence),
            1.0,
        ),
    )

    confidence_score = safe_confidence * 5.0

    # ----------------------------------------------------------
    # 6. Recency
    # ----------------------------------------------------------

    recency_score = 0.0

    if updated_at is not None:
        try:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(
                    tzinfo=timezone.utc
                )

            now = datetime.now(timezone.utc)

            age_days = max(
                0.0,
                (now - updated_at).total_seconds()
                / 86400.0,
            )

            # 0 kun = 5 ball
            # 30+ kun = deyarli 0
            recency_score = max(
                0.0,
                5.0 * (1.0 - min(age_days / 30.0, 1.0)),
            )

        except Exception:
            recency_score = 0.0

    # ----------------------------------------------------------
    # 7. Memory type bonus
    # ----------------------------------------------------------

    type_bonus = 0.0

    important_types = {
        "IMPORTANT_FACT",
        "USER_TRAIT",
        "PREFERENCE",
        "PROMISE",
        "PLAN",
        "EVENT",
        "RELATIONSHIP",
        "GROUP_FACT",
    }

    if memory_type.upper() in important_types:
        type_bonus = 2.0

    # ----------------------------------------------------------
    # Final
    # ----------------------------------------------------------

    score = (
        overlap_score
        + phrase_bonus
        + presence_score
        + importance_score
        + confidence_score
        + recency_score
        + type_bonus
    )

    return round(
        min(score, 100.0),
        3,
    )


# ==============================================================
# USER MEMORY RETRIEVAL
# ==============================================================


async def retrieve_user_memory(
    user_telegram_id: int,
    query: str | None = None,
    limit: int = 15,
) -> str:
    """
    User memory'ni AI uchun tayyor contextga aylantiradi.

    query berilsa:
        relevance scoring ishlaydi.

    query berilmasa:
        importance/confidence bo‘yicha olinadi.
    """

    limit = max(
        1,
        min(int(limit), 100),
    )

    if query:
        memories = await memory_manager.search_user_memories(
            user_telegram_id=user_telegram_id,
            search_text=query,
            limit=100,
        )
    else:
        memories = await memory_manager.get_user_memories(
            user_telegram_id=user_telegram_id,
            limit=limit,
        )

    if not memories:
        return "User haqida saqlangan xotira mavjud emas."

    if query:
        results: list[MemorySearchResult] = []

        for memory in memories:
            score = calculate_relevance(
                query=query,
                content=memory.content,
                importance=memory.importance,
                confidence=memory.confidence,
                memory_type=memory.memory_type,
                updated_at=memory.updated_at,
            )

            if score > 0:
                results.append(
                    MemorySearchResult(
                        memory=memory,
                        score=score,
                        source="user_memory",
                    )
                )

        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        results = results[:limit]

    else:
        results = [
            MemorySearchResult(
                memory=memory,
                score=100.0,
                source="user_memory",
            )
            for memory in memories[:limit]
        ]

    if not results:
        return "Query bo‘yicha mos user memory topilmadi."

    lines: list[str] = []

    for item in results:
        memory = item.memory

        lines.append(
            f"- [{memory.memory_type}] "
            f"{memory.content} "
            f"(relevance={item.score:.1f}, "
            f"importance={memory.importance}, "
            f"confidence={memory.confidence:.2f})"
        )

    return "\n".join(lines)


# ==============================================================
# GROUP MEMORY RETRIEVAL
# ==============================================================


async def retrieve_group_memory(
    group_telegram_id: int,
    query: str | None = None,
    limit: int = 15,
) -> str:
    """
    Group memory retrieval.
    """

    limit = max(
        1,
        min(int(limit), 100),
    )

    if query:
        memories = await memory_manager.search_group_memories(
            group_telegram_id=group_telegram_id,
            search_text=query,
            limit=100,
        )
    else:
        memories = await memory_manager.get_group_memories(
            group_telegram_id=group_telegram_id,
            limit=limit,
        )

    if not memories:
        return "Guruh haqida saqlangan xotira mavjud emas."

    if query:
        results: list[MemorySearchResult] = []

        for memory in memories:
            score = calculate_relevance(
                query=query,
                content=memory.content,
                importance=memory.importance,
                confidence=memory.confidence,
                memory_type=memory.memory_type,
                updated_at=memory.updated_at,
            )

            if score > 0:
                results.append(
                    MemorySearchResult(
                        memory=memory,
                        score=score,
                        source="group_memory",
                    )
                )

        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        results = results[:limit]

    else:
        results = [
            MemorySearchResult(
                memory=memory,
                score=100.0,
                source="group_memory",
            )
            for memory in memories[:limit]
        ]

    if not results:
        return "Query bo‘yicha mos group memory topilmadi."

    lines: list[str] = []

    for item in results:
        memory = item.memory

        lines.append(
            f"- [{memory.memory_type}] "
            f"{memory.content} "
            f"(relevance={item.score:.1f}, "
            f"importance={memory.importance}, "
            f"confidence={memory.confidence:.2f})"
        )

    return "\n".join(lines)


# ==============================================================
# COMBINED MEMORY RETRIEVAL
# ==============================================================


async def retrieve_relevant_memory(
    *,
    user_telegram_id: int | None = None,
    group_telegram_id: int | None = None,
    query: str = "",
    user_limit: int = 10,
    group_limit: int = 10,
) -> dict[str, Any]:
    """
    SARA uchun barcha relevant memorylarni bitta joyga yig‘adi.

    Group ichida:
        USER MEMORY
        GROUP MEMORY

    ikkalasi ham mavjud bo‘lishi mumkin.
    """

    result: dict[str, Any] = {
        "user_memory": "",
        "group_memory": "",
        "user_results": [],
        "group_results": [],
    }

    query = normalize_text(query)

    # ----------------------------------------------------------
    # USER
    # ----------------------------------------------------------

    if user_telegram_id is not None:

        if query:
            memories = await memory_manager.search_user_memories(
                user_telegram_id=user_telegram_id,
                search_text=query,
                limit=100,
            )
        else:
            memories = await memory_manager.get_user_memories(
                user_telegram_id=user_telegram_id,
                limit=user_limit,
            )

        user_results: list[MemorySearchResult] = []

        for memory in memories:

            score = (
                calculate_relevance(
                    query=query,
                    content=memory.content,
                    importance=memory.importance,
                    confidence=memory.confidence,
                    memory_type=memory.memory_type,
                    updated_at=memory.updated_at,
                )
                if query
                else 100.0
            )

            if not query or score > 0:
                user_results.append(
                    MemorySearchResult(
                        memory=memory,
                        score=score,
                        source="user_memory",
                    )
                )

        user_results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        user_results = user_results[:user_limit]

        result["user_results"] = user_results

        result["user_memory"] = _format_results(
            user_results,
            empty_text="User memory mavjud emas.",
        )

    # ----------------------------------------------------------
    # GROUP
    # ----------------------------------------------------------

    if group_telegram_id is not None:

        if query:
            memories = await memory_manager.search_group_memories(
                group_telegram_id=group_telegram_id,
                search_text=query,
                limit=100,
            )
        else:
            memories = await memory_manager.get_group_memories(
                group_telegram_id=group_telegram_id,
                limit=group_limit,
            )

        group_results: list[MemorySearchResult] = []

        for memory in memories:

            score = (
                calculate_relevance(
                    query=query,
                    content=memory.content,
                    importance=memory.importance,
                    confidence=memory.confidence,
                    memory_type=memory.memory_type,
                    updated_at=memory.updated_at,
                )
                if query
                else 100.0
            )

            if not query or score > 0:
                group_results.append(
                    MemorySearchResult(
                        memory=memory,
                        score=score,
                        source="group_memory",
                    )
                )

        group_results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        group_results = group_results[:group_limit]

        result["group_results"] = group_results

        result["group_memory"] = _format_results(
            group_results,
            empty_text="Group memory mavjud emas.",
        )

    return result


# ==============================================================
# FORMATTER
# ==============================================================


def _format_results(
    results: list[MemorySearchResult],
    *,
    empty_text: str,
) -> str:

    if not results:
        return empty_text

    lines: list[str] = []

    for item in results:
        memory = item.memory

        lines.append(
            f"- [{memory.memory_type}] "
            f"{memory.content} "
            f"(relevance={item.score:.1f}, "
            f"importance={memory.importance}, "
            f"confidence={memory.confidence:.2f})"
        )

    return "\n".join(lines)


# ==============================================================
# RAW RESULT HELPERS
# ==============================================================


async def search_user_memory_results(
    user_telegram_id: int,
    query: str,
    limit: int = 15,
) -> list[MemorySearchResult]:

    memories = await memory_manager.search_user_memories(
        user_telegram_id=user_telegram_id,
        search_text=query,
        limit=100,
    )

    results = [
        MemorySearchResult(
            memory=memory,
            score=calculate_relevance(
                query=query,
                content=memory.content,
                importance=memory.importance,
                confidence=memory.confidence,
                memory_type=memory.memory_type,
                updated_at=memory.updated_at,
            ),
            source="user_memory",
        )
        for memory in memories
    ]

    results = [
        item
        for item in results
        if item.score > 0
    ]

    results.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    return results[:max(1, min(int(limit), 100))]


async def search_group_memory_results(
    group_telegram_id: int,
    query: str,
    limit: int = 15,
) -> list[MemorySearchResult]:

    memories = await memory_manager.search_group_memories(
        group_telegram_id=group_telegram_id,
        search_text=query,
        limit=100,
    )

    results = [
        MemorySearchResult(
            memory=memory,
            score=calculate_relevance(
                query=query,
                content=memory.content,
                importance=memory.importance,
                confidence=memory.confidence,
                memory_type=memory.memory_type,
                updated_at=memory.updated_at,
            ),
            source="group_memory",
        )
        for memory in memories
    ]

    results = [
        item
        for item in results
        if item.score > 0
    ]

    results.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    return results[:max(1, min(int(limit), 100))]


# ==============================================================
# EXPORTS
# ==============================================================


__all__ = [
    "MemorySearchResult",
    "calculate_relevance",
    "retrieve_user_memory",
    "retrieve_group_memory",
    "retrieve_relevant_memory",
    "search_user_memory_results",
    "search_group_memory_results",
    ]
