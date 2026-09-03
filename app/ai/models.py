from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AIResponse:
    """
    OpenRouter / AI Engine javobi.

    text:
        AI tomonidan qaytarilgan asosiy javob.

    model:
        Haqiqatan ishlatilgan model.

    usage:
        OpenRouter token/usage ma'lumotlari.

    raw:
        OpenRouter'dan qaytgan to'liq raw response.
    """

    text: str

    model: str = ""

    usage: dict[str, Any] | None = None

    raw: dict[str, Any] | None = field(default=None)

    def __post_init__(self) -> None:
        self.text = str(self.text or "").strip()
        self.model = str(self.model or "").strip()

        if self.usage is not None and not isinstance(
            self.usage,
            dict,
        ):
            self.usage = None

        if self.raw is not None and not isinstance(
            self.raw,
            dict,
        ):
            self.raw = None

    @property
    def success(self) -> bool:
        return bool(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "usage": self.usage,
            "raw": self.raw,
        }


__all__ = ["AIResponse"]
