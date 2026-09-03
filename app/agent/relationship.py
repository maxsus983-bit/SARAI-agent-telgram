from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.database.models import Relationship
from app.database.session import SessionFactory

logger = logging.getLogger("sara.agent.relationship")


class RelationshipManager:
    """
    SARA AI foydalanuvchilar o'rtasidagi relationship tizimi.

    Score:
        -100 = juda salbiy
           0 = neytral
        +100 = juda ijobiy

    Relationship turlari:
        friend
        teammate
        rival
        family
        partner
        enemy
        acquaintance
        unknown

    Muhim:
    Relationship faqat IKKI XIL user o'rtasida mavjud bo'ladi.

    SARA o'zini o'zi bilan relationship yaratmaydi.
    """

    VALID_TYPES = {
        "friend",
        "teammate",
        "rival",
        "family",
        "partner",
        "enemy",
        "acquaintance",
        "unknown",
    }

    # =========================================================
    # NORMALIZE USERS
    # =========================================================

    @staticmethod
    def _normalize_users(
        user_a: int,
        user_b: int,
    ) -> tuple[int, int] | None:
        """
        User ID'larni normalize qiladi.

        Agar ikkala ID bir xil bo'lsa:
            None

        qaytariladi.

        Bu exception sababli butun Agent pipeline yiqilib
        ketishining oldini oladi.
        """

        try:
            user_a = int(user_a)
            user_b = int(user_b)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid relationship users | "
                "user_a=%r | user_b=%r",
                user_a,
                user_b,
            )
            return None

        if user_a <= 0 or user_b <= 0:
            logger.warning(
                "Invalid relationship user ID | "
                "user_a=%s | user_b=%s",
                user_a,
                user_b,
            )
            return None

        # O'z-o'ziga relationship kerak emas.
        if user_a == user_b:
            logger.debug(
                "Self relationship ignored | user=%s",
                user_a,
            )
            return None

        return tuple(sorted((user_a, user_b)))

    # =========================================================
    # SCORE
    # =========================================================

    @staticmethod
    def _normalize_score(
        score: float,
    ) -> float:
        """
        Score'ni -100 ... +100 oralig'ida ushlab turadi.
        """

        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0

        return max(
            -100.0,
            min(
                100.0,
                score,
            ),
        )

    # =========================================================
    # RELATIONSHIP TYPE
    # =========================================================

    @classmethod
    def _normalize_type(
        cls,
        relationship_type: str | None,
    ) -> str:
        """
        Relationship type'ni normalize qiladi.
        """

        if relationship_type is None:
            return "unknown"

        try:
            value = str(
                relationship_type
            ).strip().lower()
        except Exception:
            return "unknown"

        if value not in cls.VALID_TYPES:
            logger.warning(
                "Unknown relationship type '%s', "
                "using 'unknown'.",
                value,
            )
            return "unknown"

        return value

    # =========================================================
    # SET RELATIONSHIP
    # =========================================================

    async def set_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
        relationship_type: str,
        score: float = 0.0,
        notes: str | None = None,
    ) -> Relationship | None:
        """
        Relationship yaratadi yoki mavjudini yangilaydi.

        Bir xil user ID berilsa None qaytaradi.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:
            return None

        first, second = normalized

        relationship_type = self._normalize_type(
            relationship_type
        )

        score = self._normalize_score(
            score
        )

        async with SessionFactory() as session:

            result = await session.execute(
                select(Relationship).where(
                    Relationship.user_a == first,
                    Relationship.user_b == second,
                )
            )

            relationship = (
                result.scalar_one_or_none()
            )

            if relationship is None:

                relationship = Relationship(
                    user_a=first,
                    user_b=second,
                    relationship_type=(
                        relationship_type
                    ),
                    score=score,
                    notes=notes,
                )

                session.add(
                    relationship
                )

            else:

                relationship.relationship_type = (
                    relationship_type
                )

                relationship.score = score

                if notes is not None:
                    relationship.notes = notes

            await session.commit()

            await session.refresh(
                relationship
            )

            logger.info(
                "Relationship updated | "
                "user_a=%s | user_b=%s | "
                "type=%s | score=%.2f",
                first,
                second,
                relationship_type,
                score,
            )

            return relationship

    # =========================================================
    # GET RELATIONSHIP
    # =========================================================

    async def get_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> Relationship | None:
        """
        Ikki user o'rtasidagi relationshipni oladi.

        Bir xil user bo'lsa None.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:
            return None

        first, second = normalized

        async with SessionFactory() as session:

            result = await session.execute(
                select(Relationship).where(
                    Relationship.user_a == first,
                    Relationship.user_b == second,
                )
            )

            return (
                result.scalar_one_or_none()
            )

    # =========================================================
    # ENSURE RELATIONSHIP
    # =========================================================

    async def ensure_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> Relationship | None:
        """
        Relationship mavjud bo'lmasa yaratadi.

        Self relationship uchun None.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:
            return None

        existing = await self.get_relationship(
            user_a=user_a,
            user_b=user_b,
        )

        if existing is not None:
            return existing

        return await self.set_relationship(
            user_a=user_a,
            user_b=user_b,
            relationship_type="unknown",
            score=0.0,
        )

    # =========================================================
    # ADJUST SCORE
    # =========================================================

    async def adjust_score(
        self,
        *,
        user_a: int,
        user_b: int,
        amount: float,
    ) -> Relationship | None:
        """
        Relationship score'ni o'zgartiradi.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:
            return None

        relationship = (
            await self.get_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            amount = 0.0

        if relationship is None:

            return await self.set_relationship(
                user_a=user_a,
                user_b=user_b,
                relationship_type="unknown",
                score=amount,
            )

        new_score = self._normalize_score(
            float(relationship.score)
            + amount
        )

        return await self.set_relationship(
            user_a=user_a,
            user_b=user_b,
            relationship_type=(
                relationship.relationship_type
            ),
            score=new_score,
            notes=relationship.notes,
        )

    # =========================================================
    # REMEMBER INTERACTION
    # =========================================================

    async def remember_interaction(
        self,
        *,
        user_a: int,
        user_b: int,
        positive: bool,
        amount: float = 2.0,
    ) -> Relationship | None:
        """
        Interaction asosida relationship score'ni
        avtomatik o'zgartiradi.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:
            return None

        try:
            amount = abs(float(amount))
        except (TypeError, ValueError):
            amount = 2.0

        change = (
            amount
            if positive
            else -amount
        )

        return await self.adjust_score(
            user_a=user_a,
            user_b=user_b,
            amount=change,
        )

    # =========================================================
    # CHANGE TYPE
    # =========================================================

    async def change_type(
        self,
        *,
        user_a: int,
        user_b: int,
        relationship_type: str,
    ) -> Relationship | None:
        """
        Relationship turini o'zgartiradi.
        """

        relationship = (
            await self.ensure_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

        if relationship is None:
            return None

        return await self.set_relationship(
            user_a=user_a,
            user_b=user_b,
            relationship_type=(
                relationship_type
            ),
            score=relationship.score,
            notes=relationship.notes,
        )

    # =========================================================
    # UPDATE NOTES
    # =========================================================

    async def update_notes(
        self,
        *,
        user_a: int,
        user_b: int,
        notes: str,
    ) -> Relationship | None:
        """
        Relationship notes'ni yangilaydi.
        """

        relationship = (
            await self.ensure_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

        if relationship is None:
            return None

        return await self.set_relationship(
            user_a=user_a,
            user_b=user_b,
            relationship_type=(
                relationship.relationship_type
            ),
            score=relationship.score,
            notes=notes,
        )

    # =========================================================
    # BUILD CONTEXT
    # =========================================================

    async def build_context(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> str:
        """
        AI uchun relationship context yaratadi.

        Self relationship bo'lsa:
        relationship mavjud emas deb qaytaradi.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:

            return (
                "Bu relationship context uchun "
                "ikki xil user kerak."
            )

        relationship = (
            await self.get_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

        if relationship is None:

            return (
                "Bu ikki foydalanuvchi o'rtasida "
                "saqlangan relationship mavjud emas."
            )

        notes = (
            relationship.notes
            or "yo'q"
        )

        return (
            "RELATIONSHIP\n"
            "============\n"
            f"Type: "
            f"{relationship.relationship_type}\n"
            f"Score: "
            f"{float(relationship.score):.1f}/100\n"
            f"Notes: "
            f"{notes}"
        )

    # =========================================================
    # DELETE RELATIONSHIP
    # =========================================================

    async def delete_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> bool:
        """
        Relationshipni o'chiradi.
        """

        normalized = self._normalize_users(
            user_a,
            user_b,
        )

        if normalized is None:
            return False

        first, second = normalized

        async with SessionFactory() as session:

            result = await session.execute(
                select(Relationship).where(
                    Relationship.user_a == first,
                    Relationship.user_b == second,
                )
            )

            relationship = (
                result.scalar_one_or_none()
            )

            if relationship is None:
                return False

            await session.delete(
                relationship
            )

            await session.commit()

            logger.info(
                "Relationship deleted | "
                "user_a=%s | user_b=%s",
                first,
                second,
            )

            return True

    # =========================================================
    # DEBUG / STATS
    # =========================================================

    async def relationship_exists(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> bool:
        """
        Relationship mavjudligini tekshiradi.
        """

        relationship = (
            await self.get_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

        return relationship is not None

    @staticmethod
    def is_valid_user_pair(
        user_a: int,
        user_b: int,
    ) -> bool:
        """
        Ikki user relationship uchun yaroqlimi?
        """

        try:
            return (
                int(user_a) > 0
                and int(user_b) > 0
                and int(user_a) != int(user_b)
            )
        except (TypeError, ValueError):
            return False


# =============================================================
# GLOBAL INSTANCE
# =============================================================

relationship_manager = RelationshipManager()


__all__ = [
    "RelationshipManager",
    "relationship_manager",
]
