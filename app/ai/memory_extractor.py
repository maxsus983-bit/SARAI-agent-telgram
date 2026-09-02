from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.openrouter import OpenRouterError, openrouter
from app.memory.extractor import ExtractedMemory, parse_memory_items


logger = logging.getLogger("sara.memory_extractor")


MEMORY_EXTRACTION_PROMPT = """
You are SARA AI's memory extraction module.

Analyze the user's latest message and determine whether it contains
information worth remembering for future conversations.

Only extract genuinely useful information.

DO NOT save:
- temporary statements
- casual greetings
- ordinary questions
- jokes
- random conversation
- passwords
- API keys
- authentication tokens
- highly sensitive private information
- information about other people unless clearly relevant
- guesses or assumptions

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

If there is nothing worth remembering, return:

[]

Do not explain anything outside JSON.
""".strip()


class MemoryExtractor:

    async def extract(
        self,
        user_message: str,
        conversation_context: str = "",
    ) -> list[ExtractedMemory]:

        if not user_message.strip():
            return []

        prompt = f"""
{MEMORY_EXTRACTION_PROMPT}

RECENT CONVERSATION:
{conversation_context[-6000:]}

LATEST USER MESSAGE:
{user_message}
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
                ]
            )

        except OpenRouterError as exc:

            logger.warning(
                "Memory extraction failed: %s",
                exc,
            )

            return []

        raw_text = response.text.strip()

        # ------------------------------------------------------
        # JSON markdown wrapperni olib tashlash
        # ------------------------------------------------------

        if raw_text.startswith("```"):

            lines = raw_text.splitlines()

            if lines:

                lines = lines[1:]

            if lines and lines[-1].strip() == "```":

                lines = lines[:-1]

            raw_text = "\n".join(lines).strip()

        # ------------------------------------------------------
        # JSON parse
        # ------------------------------------------------------

        try:

            data: Any = json.loads(raw_text)

        except json.JSONDecodeError:

            logger.warning(
                "Memory extractor invalid JSON: %s",
                raw_text[:500],
            )

            return []

        return parse_memory_items(data)


memory_extractor = MemoryExtractor()
