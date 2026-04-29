"""LLM client — unified interface for MiMo (primary) and Claude (fallback)."""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger("spectra.llm")


class LLMClient:
    """Unified LLM client with MiMo as primary and Claude as fallback.

    Uses the OpenAI-compatible API format, which MiMo API supports natively.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.xiaomimimo.com/v1",
        model: str = "xiaomi/mimo-v2-pro",
        fallback_api_key: str = "",
        fallback_model: str = "claude-sonnet-4",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback_api_key = fallback_api_key
        self.fallback_model = fallback_model
        self._http = httpx.AsyncClient(timeout=120)

    async def chat(
        self,
        system: str,
        user: str,
        response_format: str = "text",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat completion request to MiMo, with Claude fallback."""
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        # Try MiMo first
        try:
            result = await self._call_openai_compatible(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if response_format == "json":
                # Validate JSON response
                json.loads(result)  # Will raise if not valid JSON
            return result
        except Exception as e:
            logger.warning(f"MiMo call failed, trying fallback: {e}")

        # Fallback to Claude via OpenRouter or direct API
        if self.fallback_api_key:
            try:
                result = await self._call_openai_compatible(
                    api_key=self.fallback_api_key,
                    base_url="https://openrouter.ai/api/v1",
                    model=self.fallback_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return result
            except Exception as e2:
                logger.error(f"Fallback LLM call also failed: {e2}")
                raise RuntimeError(f"Both LLM providers failed: {e}, {e2}")

        raise RuntimeError(f"MiMo call failed and no fallback configured: {e}")

    async def _call_openai_compatible(
        self,
        api_key: str,
        base_url: str,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
    ) -> str:
        """Make an OpenAI-compatible chat completion request."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = await self._http.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def close(self) -> None:
        await self._http.aclose()