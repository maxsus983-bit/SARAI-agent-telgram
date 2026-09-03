from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.ai.models import AIResponse
from app.config.settings import settings


logger = logging.getLogger("sara.openrouter")


OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)


class OpenRouterError(Exception):
    """OpenRouter bilan bog'liq xato."""


class OpenRouterClient:
    """
    OpenRouter API client.

    SARA AI uchun barcha AI requestlar shu client orqali
    o'tadi.
    """

    def __init__(self) -> None:
        self.api_key = settings.openrouter_api_key.strip()

        self.primary_model = (
            settings.openrouter_model.strip()
        )

        self.fallback_model = (
            settings.openrouter_fallback_model.strip()
        )

    # ==========================================================
    # HEADERS
    # ==========================================================

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise OpenRouterError(
                "OPENROUTER_API_KEY sozlanmagan."
            )

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/",
            "X-Title": "SARA AI Telegram Assistant",
        }

    # ==========================================================
    # REQUEST
    # ==========================================================

    @retry(
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.NetworkError,
            )
        ),
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=8,
        ),
        reraise=True,
    )
    async def _request(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
    ) -> AIResponse:

        model = str(model).strip()

        if not model:
            raise OpenRouterError(
                "OpenRouter model bo'sh."
            )

        if not messages:
            raise OpenRouterError(
                "OpenRouter messages bo'sh."
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": max(
                0.0,
                min(float(temperature), 2.0),
            ),
        }

        timeout = httpx.Timeout(
            connect=10.0,
            read=90.0,
            write=20.0,
            pool=10.0,
        )

        try:

            async with httpx.AsyncClient(
                timeout=timeout
            ) as client:

                response = await client.post(
                    OPENROUTER_URL,
                    headers=self._headers(),
                    json=payload,
                )

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
        ):
            raise

        except httpx.HTTPError as exc:

            raise OpenRouterError(
                f"OpenRouter HTTP client xatosi: "
                f"{type(exc).__name__}"
            ) from exc

        # ------------------------------------------------------
        # HTTP ERROR
        # ------------------------------------------------------

        if response.status_code >= 400:

            error_text = response.text[:1000]

            if response.status_code == 401:

                raise OpenRouterError(
                    "OpenRouter API key noto'g'ri "
                    "yoki yaroqsiz."
                )

            if response.status_code == 403:

                raise OpenRouterError(
                    "OpenRouter request rad etildi."
                )

            if response.status_code == 429:

                raise OpenRouterError(
                    "OpenRouter rate limitga tushdi."
                )

            if response.status_code >= 500:

                raise OpenRouterError(
                    f"OpenRouter server xatosi "
                    f"HTTP {response.status_code}."
                )

            raise OpenRouterError(
                f"OpenRouter HTTP "
                f"{response.status_code}: "
                f"{error_text}"
            )

        # ------------------------------------------------------
        # JSON
        # ------------------------------------------------------

        try:
            data: Any = response.json()

        except ValueError as exc:

            raise OpenRouterError(
                "OpenRouter JSON bo'lmagan javob qaytardi."
            ) from exc

        if not isinstance(data, dict):

            raise OpenRouterError(
                "OpenRouter response object emas."
            )

        # ------------------------------------------------------
        # API ERROR OBJECT
        # ------------------------------------------------------

        if data.get("error"):

            error = data.get("error")

            if isinstance(error, dict):

                message = str(
                    error.get(
                        "message",
                        "Unknown OpenRouter error",
                    )
                )

            else:

                message = str(error)

            raise OpenRouterError(
                f"OpenRouter API error: {message[:800]}"
            )

        # ------------------------------------------------------
        # CHOICES
        # ------------------------------------------------------

        choices = data.get("choices")

        if not isinstance(choices, list) or not choices:

            raise OpenRouterError(
                "OpenRouter javobida choices mavjud emas."
            )

        first_choice = choices[0]

        if not isinstance(first_choice, dict):

            raise OpenRouterError(
                "OpenRouter choice noto'g'ri formatda."
            )

        message = first_choice.get("message")

        if not isinstance(message, dict):

            raise OpenRouterError(
                "OpenRouter message noto'g'ri formatda."
            )

        content = message.get("content")

        # ------------------------------------------------------
        # CONTENT
        # ------------------------------------------------------

        if isinstance(content, str):

            text = content

        elif isinstance(content, list):

            parts: list[str] = []

            for item in content:

                if isinstance(item, str):
                    parts.append(item)
                    continue

                if isinstance(item, dict):

                    text_value = item.get("text")

                    if text_value is not None:
                        parts.append(
                            str(text_value)
                        )

            text = "".join(parts)

        elif content is None:

            text = ""

        else:

            text = str(content)

        text = text.strip()

        if not text:

            raise OpenRouterError(
                "AI bo'sh javob qaytardi."
            )

        # ------------------------------------------------------
        # USAGE
        # ------------------------------------------------------

        usage = data.get("usage")

        if not isinstance(usage, dict):
            usage = None

        return AIResponse(
            text=text,
            model=str(
                data.get("model") or model
            ),
            usage=usage,
            raw=data,
        )

    # ==========================================================
    # CHAT
    # ==========================================================

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
    ) -> AIResponse:

        if not self.api_key:

            raise OpenRouterError(
                "OPENROUTER_API_KEY sozlanmagan."
            )

        if not self.primary_model:

            raise OpenRouterError(
                "OPENROUTER_MODEL sozlanmagan."
            )

        # ------------------------------------------------------
        # PRIMARY
        # ------------------------------------------------------

        try:

            result = await self._request(
                model=self.primary_model,
                messages=messages,
                temperature=temperature,
            )

            logger.debug(
                "OpenRouter primary model success: %s",
                result.model,
            )

            return result

        except Exception as primary_error:

            logger.warning(
                "Primary OpenRouter model failed: %s",
                type(primary_error).__name__,
            )

            # Fallback yo'q bo'lsa
            if not self.fallback_model:

                if isinstance(
                    primary_error,
                    OpenRouterError,
                ):
                    raise

                raise OpenRouterError(
                    "Asosiy AI model ishlamadi."
                ) from primary_error

        # ------------------------------------------------------
        # FALLBACK
        # ------------------------------------------------------

        try:

            logger.info(
                "Trying OpenRouter fallback model: %s",
                self.fallback_model,
            )

            result = await self._request(
                model=self.fallback_model,
                messages=messages,
                temperature=temperature,
            )

            logger.info(
                "OpenRouter fallback model success: %s",
                result.model,
            )

            return result

        except Exception as fallback_error:

            logger.error(
                "Fallback OpenRouter model failed: %s",
                type(fallback_error).__name__,
            )

            raise OpenRouterError(
                "Asosiy va fallback AI modellar "
                "ishlamadi."
            ) from fallback_error


# ==========================================================
# GLOBAL CLIENT
# ==========================================================

openrouter = OpenRouterClient()


__all__ = [
    "OPENROUTER_URL",
    "OpenRouterError",
    "OpenRouterClient",
    "openrouter",
                ]
