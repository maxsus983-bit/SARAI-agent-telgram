from __future__ import annotations

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


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    pass


class OpenRouterClient:

    def __init__(self) -> None:

        self.api_key = settings.openrouter_api_key

        self.primary_model = settings.openrouter_model

        self.fallback_model = (
            settings.openrouter_fallback_model
        )

    def _headers(self) -> dict[str, str]:

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/",
            "X-Title": "SARA AI Telegram Assistant",
        }

    @retry(
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError)
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
        model: str,
        messages: list[dict[str, Any]],
    ) -> AIResponse:

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }

        timeout = httpx.Timeout(
            connect=10.0,
            read=90.0,
            write=20.0,
            pool=10.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.post(
                OPENROUTER_URL,
                headers=self._headers(),
                json=payload,
            )

            if response.status_code >= 400:

                raise OpenRouterError(
                    f"OpenRouter HTTP "
                    f"{response.status_code}: "
                    f"{response.text[:500]}"
                )

            data = response.json()

        try:
            text = data["choices"][0]["message"]["content"]

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:

            raise OpenRouterError(
                "OpenRouter javobi noto'g'ri formatda."
            ) from exc

        if isinstance(text, list):

            text = "".join(
                str(item)
                for item in text
            )

        text = str(text).strip()

        if not text:

            raise OpenRouterError(
                "AI bo'sh javob qaytardi."
            )

        return AIResponse(
            text=text,
            model=model,
            usage=data.get("usage"),
            raw=data,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
    ) -> AIResponse:

        if not self.api_key:
            raise OpenRouterError(
                "OPENROUTER_API_KEY sozlanmagan."
            )

        if not self.primary_model:
            raise OpenRouterError(
                "OPENROUTER_MODEL sozlanmagan."
            )

        try:

            return await self._request(
                model=self.primary_model,
                messages=messages,
            )

        except Exception as primary_error:

            if not self.fallback_model:
                raise OpenRouterError(
                    f"Asosiy AI model ishlamadi: "
                    f"{primary_error}"
                ) from primary_error

            try:

                return await self._request(
                    model=self.fallback_model,
                    messages=messages,
                )

            except Exception as fallback_error:

                raise OpenRouterError(
                    "Asosiy va fallback AI modellar "
                    "ishlamadi."
                ) from fallback_error


openrouter = OpenRouterClient()
