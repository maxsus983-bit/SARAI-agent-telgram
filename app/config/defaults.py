"""
SARA AI default configuration.

Bu faylda SARA AI personality va default
agent sozlamalari saqlanadi.
"""

from __future__ import annotations


# ============================================================
# SARA PERSONALITY
# ============================================================

personality: dict[str, int] = {
    # Hazil darajasi
    "humor_level": 85,

    # Dark humor
    "dark_humor": 70,

    # Kinoya / sarcasm
    "sarcasm": 65,

    # Do‘stona munosabat
    "friendliness": 75,

    # Jiddiylik
    "seriousness": 45,

    # Tajovuzkorlik
    "aggression": 30,

    # Tashabbuskorlik
    "initiative": 80,

    # Javob uzunligi
    "verbosity": 55,

    # Emoji ishlatish
    "emoji_usage": 45,

    # Rasmiylik
    "formality": 15,
}


# ============================================================
# DEFAULT AGENT SETTINGS
# ============================================================

DEFAULT_AGENT_SETTINGS: dict[str, object] = {
    "memory_enabled": True,
    "proactive_enabled": True,
    "group_mode_enabled": True,
    "bot_to_bot_enabled": True,
    "reminder_enabled": True,
    "media_enabled": True,
}


# ============================================================
# MEMORY SETTINGS
# ============================================================

DEFAULT_MEMORY_SETTINGS: dict[str, int] = {
    "max_recent_messages": 100,
    "max_memory_results": 15,
    "max_context_tokens": 12000,
}


# ============================================================
# RATE LIMIT SETTINGS
# ============================================================

DEFAULT_RATE_LIMIT_SETTINGS: dict[str, float] = {
    "user_rate_limit_seconds": 1.0,
    "group_rate_limit_seconds": 1.0,
}


# ============================================================
# PROACTIVE AGENT SETTINGS
# ============================================================

DEFAULT_PROACTIVE_SETTINGS: dict[str, int] = {
    "proactive_cooldown_seconds": 300,
    "quiet_group_interval_seconds": 3600,
}


# ============================================================
# BOT-TO-BOT SETTINGS
# ============================================================

DEFAULT_BOT_SETTINGS: dict[str, int] = {
    "max_bot_chain": 5,
    "bot_to_bot_cooldown_seconds": 30,
}


# ============================================================
# LANGUAGE SETTINGS
# ============================================================

SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "uz",
    "ru",
    "en",
)

DEFAULT_LANGUAGE = "uz"


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "personality",
    "DEFAULT_AGENT_SETTINGS",
    "DEFAULT_MEMORY_SETTINGS",
    "DEFAULT_RATE_LIMIT_SETTINGS",
    "DEFAULT_PROACTIVE_SETTINGS",
    "DEFAULT_BOT_SETTINGS",
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
]
