import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import get_settings
from loguru import logger


settings = get_settings()


class LLMProvider(str, Enum):
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    NVIDIA = "nvidia"
    GOOGLE = "google"


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    provider: LLMProvider
    max_tokens: int = 4096
    supports_json: bool = True
    supports_streaming: bool = True
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


# Model configurations
MODEL_CONFIGS = {
    # OpenAI models
    "gpt-4o": ModelConfig("gpt-4o", LLMProvider.OPENAI, 4096, True, True, 0.005, 0.015),
    "gpt-4o-mini": ModelConfig("gpt-4o-mini", LLMProvider.OPENAI, 4096, True, True, 0.00015, 0.0006),
    "gpt-4-turbo": ModelConfig("gpt-4-turbo", LLMProvider.OPENAI, 4096, True, True, 0.01, 0.03),
    "gpt-3.5-turbo": ModelConfig("gpt-3.5-turbo", LLMProvider.OPENAI, 4096, True, True, 0.0005, 0.0015),
    
    # OpenRouter models (accessible via OpenRouter)
    "anthropic/claude-3.5-sonnet": ModelConfig("anthropic/claude-3.5-sonnet", LLMProvider.OPENROUTER, 8192, True, True, 0.003, 0.015),
    "anthropic/claude-3-haiku": ModelConfig("anthropic/claude-3-haiku", LLMProvider.OPENROUTER, 4096, True, True, 0.00025, 0.00125),
    "anthropic/claude-3-opus": ModelConfig("anthropic/claude-3-opus", LLMProvider.OPENROUTER, 4096, True, True, 0.015, 0.075),
    "google/gemini-pro-1.5": ModelConfig("google/gemini-pro-1.5", LLMProvider.OPENROUTER, 8192, True, True, 0.00125, 0.005),
    "google/gemini-flash-1.5": ModelConfig("google/gemini-flash-1.5", LLMProvider.OPENROUTER, 8192, True, True, 0.000075, 0.0003),
    "meta-llama/llama-3.1-405b": ModelConfig("meta-llama/llama-3.1-405b", LLMProvider.OPENROUTER, 8192, True, True, 0.003, 0.003),
    "meta-llama/llama-3.1-70b": ModelConfig("meta-llama/llama-3.1-70b", LLMProvider.OPENROUTER, 8192, True, True, 0.0008, 0.0008),
    "meta-llama/llama-3.1-8b": ModelConfig("meta-llama/llama-3.1-8b", LLMProvider.OPENROUTER, 8192, True, True, 0.00018, 0.00018),
    "mistralai/mistral-large": ModelConfig("mistralai/mistral-large", LLMProvider.OPENROUTER, 8192, True, True, 0.002, 0.006),
    "mistralai/mistral-nemo": ModelConfig("mistralai/mistral-nemo", LLMProvider.OPENROUTER, 8192, True, True, 0.00015, 0.00015),
    "qwen/qwen-2.5-72b": ModelConfig("qwen/qwen-2.5-72b", LLMProvider.OPENROUTER, 8192, True, True, 0.0008, 0.0008),
    "deepseek/deepseek-chat": ModelConfig("deepseek/deepseek-chat", LLMProvider.OPENROUTER, 8192, True, True, 0.00014, 0.00028),
    "microsoft/wizardlm-2-8x22b": ModelConfig("microsoft/wizardlm-2-8x22b", LLMProvider.OPENROUTER, 8192, True, True, 0.0008, 0.0008),
    
    # NVIDIA models (via NVIDIA API)
    "nvidia/nemotron-3-ultra": ModelConfig("nvidia/nemotron-3-ultra", LLMProvider.NVIDIA, 4096, True, True, 0.0, 0.0),
    "nvidia/nemotron-4-340b": ModelConfig("nvidia/nemotron-4-340b", LLMProvider.NVIDIA, 8192, True, True, 0.0, 0.0),
    "nvidia/llama-3.1-nemotron-70b": ModelConfig("nvidia/llama-3.1-nemotron-70b", LLMProvider.NVIDIA, 8192, True, True, 0.0, 0.0),
    "nvidia/mistral-7b": ModelConfig("nvidia/mistral-7b", LLMProvider.NVIDIA, 4096, True, True, 0.0, 0.0),
    
    # Google models (direct API)
    "gemini-1.5-pro": ModelConfig("gemini-1.5-pro", LLMProvider.GOOGLE, 8192, True, True, 0.00125, 0.005),
    "gemini-1.5-flash": ModelConfig("gemini-1.5-flash", LLMProvider.GOOGLE, 8192, True, True, 0.000075, 0.0003),
    "gemini-1.0-pro": ModelConfig("gemini-1.0-pro", LLMProvider.GOOGLE, 4096, True, True, 0.0005, 0.0015),
    "gemini-2.0-flash-exp": ModelConfig("gemini-2.0-flash-exp", LLMProvider.GOOGLE, 8192, True, True, 0.000075, 0.0003),
}


class LLMClient:
    """Unified LLM client with OpenAI, OpenRouter, NVIDIA, and Google support, automatic fallback."""
    
    def __init__(
        self,
        primary_model: str = None,
        fallback_model: str = None,
        primary_provider: LLMProvider = None,
        fallback_provider: LLMProvider = None,
        api_key: str = None,
        openrouter_key: str = None,
        nvidia_key: str = None,
        google_key: str = None,
    ):
        # Use config settings if not provided
        self.primary_model = primary_model or settings.OPENAI_CHAT_MODEL
        self.fallback_model = fallback_model or settings.OPENROUTER_CHAT_MODEL
        
        # Parse provider from config
        provider_str = settings.LLM_PROVIDER.lower()
        self.primary_provider = primary_provider or LLMProvider(provider_str) if provider_str in [p.value for p in LLMProvider] else LLMProvider.OPENAI
        
        # Parse fallback chain
        fallback_chain = [p.strip() for p in settings.LLM_FALLBACK_CHAIN.split(",")]
        self.fallback_providers = [LLMProvider(p) for p in fallback_chain if p in [p.value for p in LLMProvider]]
        
        self.fallback_enabled = settings.LLM_FALLBACK_ENABLED
        
        # Initialize clients
        self.openai_client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            base_url="https://api.openai.com/v1"
        )
        
        self.openrouter_client = None
        if getattr(settings, 'OPENROUTER_API_KEY', None):
            self.openrouter_client = AsyncOpenAI(
                api_key=openrouter_key or settings.OPENROUTER_API_KEY,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://github.com/instagpt-graphrag",
                    "X-Title": "InstaGPT GraphRAG"
                }
            )
        
        self.nvidia_client = None
        if getattr(settings, 'NVIDIA_API_KEY', None):
            self.nvidia_client = AsyncOpenAI(
                api_key=nvidia_key or settings.NVIDIA_API_KEY,
                base_url="https://integrate.api.nvidia.com/v1"
            )
        
        self.google_client = None
        if getattr(settings, 'GOOGLE_API_KEY', None):
            self.google_client = AsyncOpenAI(
                api_key=google_key or settings.GOOGLE_API_KEY,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
        
        # Track usage
        self.usage_stats = {
            "primary": {"calls": 0, "tokens": 0, "errors": 0},
            "fallback": {"calls": 0, "tokens": 0, "errors": 0},
            **{p.value: {"calls": 0, "tokens": 0, "errors": 0} for p in LLMProvider}
        }
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((Exception,))
    )
    async def _chat_completion_single(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.2,
        max_tokens: int = None,
        response_format: Dict = None,
        provider: LLMProvider = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Single provider attempt - no fallback logic."""
        client, model_name = self._get_client_and_model_for_provider(provider, model)
        config = self._get_config(model_name)
        
        if response_format and not config.supports_json:
            logger.warning(f"Model {model_name} doesn't support JSON format, ignoring")
            response_format = None
        
        request_params = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        if max_tokens:
            request_params["max_tokens"] = min(max_tokens, config.max_tokens)
        
        if response_format:
            request_params["response_format"] = response_format
        
        response = await client.chat.completions.create(**request_params)
        
        return {
            "content": response.choices[0].message.content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            "model": model_name,
            "provider": provider.value,
            "finish_reason": response.choices[0].finish_reason
        }
    
    def _get_config(self, model: str) -> ModelConfig:
        """Get model configuration."""
        return MODEL_CONFIGS.get(model, ModelConfig(model, LLMProvider.OPENAI))

    def _get_client_and_model_for_provider(self, provider: LLMProvider, model: str = None) -> tuple:
        """Get client and model for specific provider."""
        model = model or (self.fallback_model if provider != self.primary_provider else self.primary_model)
        
        if provider == LLMProvider.OPENROUTER and self.openrouter_client:
            return self.openrouter_client, model
        elif provider == LLMProvider.NVIDIA and self.nvidia_client:
            return self.nvidia_client, model
        elif provider == LLMProvider.GOOGLE and self.google_client:
            return self.google_client, model
        elif provider == LLMProvider.OPENAI:
            return self.openai_client, model
        
        return self.openai_client, self.primary_model
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.2,
        max_tokens: int = None,
        response_format: Dict = None,
        use_fallback: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion with automatic fallback chain.
        
        Fallback chain from config: LLM_FALLBACK_CHAIN
        """
        # Build fallback chain from config
        chain = [self.primary_provider] + [p for p in self.fallback_providers if p != self.primary_provider]
        
        # If use_fallback is True, skip primary
        if use_fallback:
            chain = chain[1:]
        
        # Filter to only available clients
        available_chain = []
        for p in chain:
            if p == LLMProvider.OPENAI:
                available_chain.append(p)
            elif p == LLMProvider.OPENROUTER and self.openrouter_client:
                available_chain.append(p)
            elif p == LLMProvider.NVIDIA and self.nvidia_client:
                available_chain.append(p)
            elif p == LLMProvider.GOOGLE and self.google_client:
                available_chain.append(p)
        
        if not available_chain:
            available_chain = [LLMProvider.OPENAI]
        
        last_error = None
        
        for i, provider in enumerate(available_chain):
            try:
                result = await self._chat_completion_single(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    provider=provider,
                    **kwargs
                )
                
                # Track usage
                key = "fallback" if i > 0 else "primary"
                self.usage_stats["primary" if i == 0 else "fallback"]["calls"] += 1
                self.usage_stats["primary" if i == 0 else "fallback"]["tokens"] += result["usage"]["total_tokens"]
                
                if i > 0:
                    logger.info(f"Fallback succeeded with {provider.value} ({result['model']})")
                
                return result
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {provider.value} failed: {e}. Trying next...")
                continue
        
        # All providers failed
        self.usage_stats["primary"]["errors"] += 1
        raise last_error or Exception("All LLM providers failed")
    
    async def chat_completion_with_fallback(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Try primary, then fallback automatically.
        This is the main method to use for most calls.
        """
        return await self.chat_completion(messages=messages, **kwargs)
    
    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get structured JSON output using function calling or response_format.
        Falls back to prompt-based JSON if function calling not available.
        """
        config = self._get_config(kwargs.get("model", self.primary_model))
        
        if config.supports_json:
            return await self.chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
                **kwargs
            )
        else:
            # Fallback: add JSON instruction to prompt
            json_instruction = "\n\nRespond ONLY with valid JSON matching this schema:\n" + json.dumps(schema, indent=2)
            messages_with_json = messages + [{"role": "system", "content": json_instruction}]
            return await self.chat_completion(messages=messages_with_json, **kwargs)
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.2,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        client, model_name = self._get_client_and_model()
        config = self._get_config(model_name)
        
        if not config.supports_streaming:
            # Fall back to non-streaming
            result = await self.chat_completion(messages=messages, model=model_name, temperature=temperature, **kwargs)
            yield result["content"]
            return
        
        request_params = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        
        try:
            stream = await client.chat.completions.create(**request_params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            # Fall back to non-streaming
            result = await self.chat_completion(messages=messages, model=model_name, temperature=temperature, **kwargs)
            yield result["content"]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return self.usage_stats.copy()
    
    def reset_stats(self):
        """Reset usage statistics."""
        self.usage_stats = {
            "primary": {"calls": 0, "tokens": 0, "errors": 0},
            "fallback": {"calls": 0, "tokens": 0, "errors": 0}
        }
    
    async def close(self):
        """Close all clients."""
        await self.openai_client.close()
        if self.openrouter_client:
            await self.openrouter_client.close()
        if self.nvidia_client:
            await self.nvidia_client.close()
        if self.google_client:
            await self.google_client.close()


# Convenience function for quick usage
async def quick_chat(
    prompt: str,
    system: str = None,
    model: str = None,
    json_mode: bool = False,
    **kwargs
) -> str:
    """Quick one-off chat completion."""
    client = LLMClient()
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        if json_mode:
            result = await client.structured_output(messages, {}, model=model, **kwargs)
        else:
            result = await client.chat_completion(messages=messages, model=model, **kwargs)
        
        return result["content"]
    finally:
        await client.close()


# Example usage and testing
if __name__ == "__main__":
    import json
    
    async def test():
        client = LLMClient(
            primary_model="gpt-4o-mini",
            fallback_model="anthropic/claude-3-haiku"
        )
        
        # Test basic completion
        print("Testing basic completion...")
        result = await client.chat_completion([
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one sentence."}
        ])
        print(f"Result: {result['content']}")
        print(f"Model: {result['model']}, Provider: {result['provider']}")
        
        # Test JSON mode
        print("\nTesting JSON mode...")
        result = await client.structured_output([
            {"role": "system", "content": "Extract entities as JSON."},
            {"role": "user", "content": "React and TypeScript are popular for frontend."}
        ], {
            "type": "object",
            "properties": {
                "entities": {"type": "array", "items": {"type": "string"}}
            }
        })
        print(f"Result: {result['content']}")
        
        print(f"\nUsage stats: {client.get_usage_stats()}")
        await client.close()
    
    asyncio.run(test())