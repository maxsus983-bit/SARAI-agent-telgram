from __future__ import annotations

import logging

from sqlalchemy import select

from app.database.models import Relationship
from app.database.session import SessionFactory

logger = logging.getLogger("sara.agent.relationship")


class RelationshipManager:

    async def set_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
        relationship_type: str,
        score: float = 0.0,
        notes: str | None = None,
    ) -> Relationship:

        first, second = sorted(
            (user_a, user_b)
        )

        async with SessionFactory() as session:

            result = await session.execute(
                select(Relationship).where(
                    Relationship.user_a == first,
                    Relationship.user_b == second,
                )
            )

            relationship = result.scalar_one_or_none()

            if relationship is None:
                relationship = Relationship(
                    user_a=first,
                    user_b=second,
                    relationship_type=relationship_type,
                    score=max(-100.0, min(100.0, score)),
                    notes=notes,
                )

                session.add(relationship)

            else:
                relationship.relationship_type = (
                    relationship_type
                )

                relationship.score = max(
                    -100.0,
                    min(100.0, score),
                )

                if notes is not None:
                    relationship.notes = notes

            await session.commit()
            await session.refresh(relationship)

            return relationship

    async def get_relationship(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> Relationship | None:

        first, second = sorted(
            (user_a, user_b)
        )

        async with SessionFactory() as session:

            result = await session.execute(
                select(Relationship).where(
                    Relationship.user_a == first,
                    Relationship.user_b == second,
                )
            )

            return result.scalar_one_or_none()

    async def adjust_score(
        self,
        *,
        user_a: int,
        user_b: int,
        amount: float,
    ) -> Relationship:

        relationship = await self.get_relationship(
            user_a=user_a,
            user_b=user_b,
        )

        if relationship is None:
            return await self.set_relationship(
                user_a=user_a,
                user_b=user_b,
                relationship_type="unknown",
                score=amount,
            )

        new_score = max(
            -100.0,
            min(
                100.0,
                relationship.score + amount,
            ),
        )

        return await self.set_relationship(
            user_a=user_a,
            user_b=user_b,
            relationship_type=relationship.relationship_type,
            score=new_score,
            notes=relationship.notes,
        )

    async def build_context(
        self,
        *,
        user_a: int,
        user_b: int,
    ) -> str:

        relationship = await self.get_relationship(
            user_a=user_a,
            user_b=user_b,
        )

        if relationship is None:
            return (
                "Bu ikki foydalanuvchi o'rtasida "
                "saqlangan relationship yo'q."
            )

        return (
            f"Relationship: "
            f"{relationship.relationship_type}\n"
            f"Score: {relationship.score:.1f}/100\n"
            f"Notes: {relationship.notes or 'yo'q'}"
        )


relationship_manager = RelationshipManager()
