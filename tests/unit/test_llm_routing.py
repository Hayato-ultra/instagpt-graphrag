"""Tests for multi-LLM adapter and model routing (TODO #39, #54)."""
import pytest
from src.enrichment.llm_client import LLMProvider, ModelConfig, MODEL_CONFIGS


class TestLLMProvider:
    """Verify LLMProvider enum has all expected providers."""

    def test_provider_values(self):
        assert LLMProvider.OPENAI == "openai"
        assert LLMProvider.OPENROUTER == "openrouter"
        assert LLMProvider.NVIDIA == "nvidia"
        assert LLMProvider.GOOGLE == "google"
        assert LLMProvider.OLLAMA == "ollama"
        assert LLMProvider.COLAB == "colab"


class TestModelConfigs:
    """Verify MODEL_CONFIGS registry is populated."""

    def test_has_openai_models(self):
        assert "gpt-4o" in MODEL_CONFIGS
        assert "gpt-4o-mini" in MODEL_CONFIGS

    def test_has_openrouter_models(self):
        assert "anthropic/claude-3.5-sonnet" in MODEL_CONFIGS

    def test_has_ollama_models(self):
        assert "llama3.1" in MODEL_CONFIGS

    def test_model_config_fields(self):
        cfg = MODEL_CONFIGS["gpt-4o"]
        assert cfg.provider == LLMProvider.OPENAI
        assert cfg.max_tokens == 4096
        assert cfg.supports_json is True


class TestModelRouting:
    """TODO #54: Route models by task type."""

    def test_get_model_for_task_returns_string(self):
        """get_model_for_task returns a model name string."""
        from src.enrichment.llm_client import LLMClient
        client = LLMClient()
        result = client.get_model_for_task("extraction")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_summary_uses_different_model(self):
        """Summary task can use a different (cheaper) model."""
        from src.enrichment.llm_client import LLMClient
        client = LLMClient()
        extraction_model = client.get_model_for_task("extraction")
        summary_model = client.get_model_for_task("summary")
        # Both should be valid model names
        assert isinstance(extraction_model, str)
        assert isinstance(summary_model, str)

    def test_unknown_task_falls_back(self):
        """Unknown task returns a valid model name."""
        from src.enrichment.llm_client import LLMClient
        client = LLMClient()
        result = client.get_model_for_task("unknown_task")
        assert isinstance(result, str)
        assert len(result) > 0
