from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AIResponse:
    text: str
    model: str
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
