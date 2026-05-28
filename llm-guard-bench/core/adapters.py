from __future__ import annotations

import asyncio
import os
import pathlib
from abc import ABC, abstractmethod
from typing import Any, Optional

import aiohttp
from groq import AsyncGroq


class BaseAdapter(ABC):
    """Abstract interface for model provider adapters."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        override_temperature: float = None,
    ) -> str:
        """Generate a model response for the provided prompts."""
        raise NotImplementedError


class OllamaAdapter(BaseAdapter):
    """Async adapter for Ollama local HTTP API."""

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 180.0,
        default_temperature: float = 0.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.default_temperature = default_temperature

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        override_temperature: float = None,
    ) -> str:
        url = f"{self.base_url}/api/chat"
        temperature = (
            override_temperature
            if override_temperature is not None
            else self.default_temperature
        )
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status >= 400:
                        body = await response.text()
                        raise RuntimeError(
                            f"Ollama API error (status={response.status}): {body}"
                        )

                    data = await response.json(content_type=None)
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Ollama request timed out after {self.timeout_seconds} seconds"
            ) from exc
        except aiohttp.ClientConnectionError as exc:
            raise RuntimeError(f"Ollama connection error: {exc}") from exc
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Ollama HTTP client error: {exc}") from exc
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Unexpected Ollama adapter error: {exc}") from exc

        try:
            message = data.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content

            response_text = data.get("response")
            if isinstance(response_text, str) and response_text.strip():
                return response_text

            raise RuntimeError(f"Ollama response missing expected content: {data}")
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to parse Ollama response: {exc}") from exc


class GroqAdapter(BaseAdapter):
    """Async adapter for Groq chat completions."""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        timeout_seconds: float = 180.0,
        default_temperature: float = 0.0,
    ) -> None:
        if not api_key:
            raise RuntimeError("Groq API key is required")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.default_temperature = default_temperature
        self.client = AsyncGroq(api_key=api_key, timeout=timeout_seconds)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        override_temperature: float = None,
    ) -> str:
        temperature = (
            override_temperature
            if override_temperature is not None
            else self.default_temperature
        )

        try:
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
        except asyncio.TimeoutError as exc:
            raise RuntimeError(
                f"Groq request timed out after {self.timeout_seconds} seconds"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Groq API request failed: {exc}") from exc

        try:
            choices = getattr(completion, "choices", None)
            if not choices:
                raise RuntimeError("Groq completion did not return any choices")

            content = choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise RuntimeError("Groq completion returned empty content")
            return content
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to parse Groq response: {exc}") from exc


def _get_default_ollama_url() -> str:
    """
    Determine Ollama base URL based on environment and execution context.
    
    Priority:
    1. OLLAMA_BASE_URL environment variable (explicit override)
    2. OLLAMA_ENDPOINT environment variable (Docker Compose default)
    3. host.docker.internal:11434 if running in Docker (detected by /.dockerenv)
    4. localhost:11434 if running locally
    """
    # Priority 1: Explicit environment variable
    if env_url := os.getenv("OLLAMA_BASE_URL"):
        return env_url
    
    # Priority 2: Docker Compose OLLAMA_ENDPOINT
    if env_url := os.getenv("OLLAMA_ENDPOINT"):
        return env_url
    
    # Priority 3: Running in Docker container (check for /.dockerenv marker)
    if pathlib.Path("/.dockerenv").exists():
        return "http://host.docker.internal:11434"
    
    # Fallback: localhost (for local development)
    return "http://localhost:11434"


def get_adapter(provider: str, model_name: str, api_key: str = None) -> BaseAdapter:
    """Factory for provider-specific adapters."""
    normalized = (provider or "").strip().lower()

    if normalized == "ollama":
        base_url = _get_default_ollama_url()
        # এখানে explicit ভাবে timeout_seconds=180.0 পাস করে দিচ্ছি
        return OllamaAdapter(model_name=model_name, base_url=base_url, timeout_seconds=180.0)

    if normalized == "groq":
        if not api_key:
            raise RuntimeError("API key is required for Groq adapter")
        return GroqAdapter(model_name=model_name, api_key=api_key, timeout_seconds=180.0)

    raise RuntimeError(f"Unsupported provider: {provider}")