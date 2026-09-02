from __future__ import annotations

import logging

from sqlalchemy import select

from app.database.models import Relationship
from app.database.session import SessionFactory

logger = logging.getLogger(
    "sara.agent.relationship"
)


class RelationshipManager:
    """
    Foydalanuvchilar o'rtasidagi relationship tizimi.

    Score:
        -100 = juda salbiy
         0   = neytral
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
    """

    # =========================================================
    # NORMALIZE
    # =========================================================

    @staticmethod
    def _normalize_users(
        user_a: int,
        user_b: int,
    ) -> tuple[int, int]:

        if user_a == user_b:
            raise ValueError(
                "Relationship uchun ikki xil "
                "user kerak."
            )

        return tuple(
            sorted(
                (user_a, user_b)
            )
        )

    @staticmethod
    def _normalize_score(
        score: float,
    ) -> float:

        return max(
            -100.0,
            min(
                100.0,
                float(score),
            ),
        )

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
    ) -> Relationship:

        first, second = (
            self._normalize_users(
                user_a,
                user_b,
            )
        )

        relationship_type = (
            relationship_type.strip().lower()
            or "unknown"
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

        first, second = (
            self._normalize_users(
                user_a,
                user_b,
            )
        )

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
    # CREATE IF NOT EXISTS
    # =========================================================

    async def ensure_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> Relationship:

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
    ) -> Relationship:

        relationship = (
            await self.get_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

        if relationship is None:

            return await self.set_relationship(
                user_a=user_a,
                user_b=user_b,
                relationship_type="unknown",
                score=amount,
            )

        new_score = self._normalize_score(
            relationship.score + amount
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
    ) -> Relationship:

        amount = abs(
            float(amount)
        )

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
    ) -> Relationship:

        relationship = (
            await self.ensure_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

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
    # NOTES
    # =========================================================

    async def update_notes(
        self,
        *,
        user_a: int,
        user_b: int,
        notes: str,
    ) -> Relationship:

        relationship = (
            await self.ensure_relationship(
                user_a=user_a,
                user_b=user_b,
            )
        )

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
    # CONTEXT
    # =========================================================

    async def build_context(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> str:

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

        return (
            "RELATIONSHIP\n"
            "============\n"
            f"Type: "
            f"{relationship.relationship_type}\n"
            f"Score: "
            f"{relationship.score:.1f}/100\n"
            f"Notes: "
            f"{relationship.notes or 'yo‘q'}"
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

        first, second = (
            self._normalize_users(
                user_a,
                user_b,
            )
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


relationship_manager = (
    RelationshipManager()
                    )
