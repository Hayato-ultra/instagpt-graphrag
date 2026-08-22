"""Pipeline version tracking (TODO #60).

Tracks pipeline_version, model_version, prompt_version, embedding_version.
"""
from __future__ import annotations

from dataclasses import dataclass

from loguru import logger


@dataclass
class PipelineVersions:
    """Version information for a pipeline run."""
    pipeline_version: str = "1.0.0"
    model_version: str = ""
    prompt_version: str = ""
    embedding_version: str = ""
    schema_version: str = "1"

    def to_dict(self) -> dict[str, str]:
        return {
            "pipeline_version": self.pipeline_version,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "embedding_version": self.embedding_version,
            "schema_version": self.schema_version,
        }


# Global version tracker
_current_versions = PipelineVersions()


def get_current_versions() -> PipelineVersions:
    """Get current pipeline versions."""
    return _current_versions


def set_versions(**kwargs) -> PipelineVersions:
    """Set pipeline versions."""
    global _current_versions
    for key, value in kwargs.items():
        if hasattr(_current_versions, key):
            setattr(_current_versions, key, value)
    logger.debug(f"Pipeline versions set: {_current_versions}")
    return _current_versions
