"""Provider-specific LLM adapters (TODO #39).

Each adapter handles provider-specific quirks and API differences.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger


class LLMAdapter(ABC):
    """Base class for provider-specific LLM adapters."""

    @abstractmethod
    def format_messages(self, messages: list[dict], **kwargs) -> list[dict]:
        """Format messages for this provider's API."""
        ...

    @abstractmethod
    def format_response(self, response: Any) -> dict:
        """Normalize response to standard format."""
        ...

    @abstractmethod
    def get_extra_kwargs(self) -> dict:
        """Get provider-specific kwargs for API calls."""
        ...


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI and compatible APIs."""

    def format_messages(self, messages: list[dict], **kwargs) -> list[dict]:
        return messages

    def format_response(self, response: Any) -> dict:
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else {},
        }

    def get_extra_kwargs(self) -> dict:
        return {}


class OpenRouterAdapter(LLMAdapter):
    """Adapter for OpenRouter API."""

    def format_messages(self, messages: list[dict], **kwargs) -> list[dict]:
        # OpenRouter uses same format as OpenAI
        return messages

    def format_response(self, response: Any) -> dict:
        # Same as OpenAI
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else {},
        }

    def get_extra_kwargs(self) -> dict:
        return {"provider": "openrouter"}


class NvidiaAdapter(LLMAdapter):
    """Adapter for NVIDIA NIM API."""

    def format_messages(self, messages: list[dict], **kwargs) -> list[dict]:
        # NVIDIA uses same format as OpenAI
        return messages

    def format_response(self, response: Any) -> dict:
        choice = response.choices[0]
        return {
            "content": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            },
        }

    def get_extra_kwargs(self) -> dict:
        return {}


class OllamaAdapter(LLMAdapter):
    """Adapter for Ollama local API."""

    def format_messages(self, messages: list[dict], **kwargs) -> list[dict]:
        # Ollama uses same format
        return messages

    def format_response(self, response: Any) -> dict:
        # Ollama response format differs
        if hasattr(response, "message"):
            return {
                "content": response.message.content or "",
                "finish_reason": "stop",
                "usage": {
                    "prompt_tokens": getattr(response, "prompt_eval_count", 0),
                    "completion_tokens": getattr(response, "eval_count", 0),
                    "total_tokens": 0,
                },
            }
        return {"content": str(response), "finish_reason": "stop", "usage": {}}

    def get_extra_kwargs(self) -> dict:
        return {"base_url": "http://localhost:11434/v1"}


# Adapter registry
ADAPTERS = {
    "openai": OpenAIAdapter(),
    "openrouter": OpenRouterAdapter(),
    "nvidia": NvidiaAdapter(),
    "ollama": OllamaAdapter(),
    "google": OpenAIAdapter(),  # Google via OpenAI-compatible endpoint
    "colab": OpenAIAdapter(),   # Colab via OpenAI-compatible endpoint
}


def get_adapter(provider: str) -> LLMAdapter:
    """Get adapter for a provider."""
    return ADAPTERS.get(provider, OpenAIAdapter())
