"""Evaluation framework for pipeline quality (TODO #38).

Provides metrics for extraction accuracy, entity resolution, and output quality.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class EvalMetrics:
    """Evaluation metrics for a pipeline run."""
    total_inputs: int = 0
    total_entities_extracted: int = 0
    valid_entities: int = 0
    hallucinated_entities: int = 0
    duplicates_detected: int = 0
    summaries_generated: int = 0
    garbled_summaries: int = 0
    steps_extracted: int = 0
    valid_steps: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def extraction_precision(self) -> float:
        """Ratio of valid entities to total extracted."""
        if self.total_entities_extracted == 0:
            return 0.0
        return self.valid_entities / self.total_entities_extracted

    @property
    def hallucination_rate(self) -> float:
        """Ratio of hallucinated entities to total extracted."""
        if self.total_entities_extracted == 0:
            return 0.0
        return self.hallucinated_entities / self.total_entities_extracted

    @property
    def summary_quality(self) -> float:
        """Ratio of non-garbled summaries to total."""
        if self.summaries_generated == 0:
            return 0.0
        return 1.0 - (self.garbled_summaries / self.summaries_generated)

    @property
    def step_quality(self) -> float:
        """Ratio of valid steps to total steps."""
        if self.steps_extracted == 0:
            return 0.0
        return self.valid_steps / self.steps_extracted

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "total_inputs": self.total_inputs,
            "total_entities_extracted": self.total_entities_extracted,
            "valid_entities": self.valid_entities,
            "hallucinated_entities": self.hallucinated_entities,
            "duplicates_detected": self.duplicates_detected,
            "summaries_generated": self.summaries_generated,
            "garbled_summaries": self.garbled_summaries,
            "steps_extracted": self.steps_extracted,
            "valid_steps": self.valid_steps,
            "extraction_precision": round(self.extraction_precision, 3),
            "hallucination_rate": round(self.hallucination_rate, 3),
            "summary_quality": round(self.summary_quality, 3),
            "step_quality": round(self.step_quality, 3),
            "errors": self.errors,
        }

    def log_summary(self) -> None:
        """Log evaluation summary."""
        logger.info(
            f"Eval: {self.total_inputs} inputs → "
            f"{self.total_entities_extracted} entities "
            f"(precision={self.extraction_precision:.1%}, "
            f"hallucination={self.hallucination_rate:.1%}), "
            f"{self.summaries_generated} summaries "
            f"(quality={self.summary_quality:.1%}), "
            f"{self.steps_extracted} steps "
            f"(quality={self.step_quality:.1%})"
        )


class PipelineEvaluator:
    """Track and report pipeline quality metrics (TODO #38)."""

    def __init__(self) -> None:
        self.metrics = EvalMetrics()
        self._run_metrics: list[EvalMetrics] = []

    def record_entity(
        self,
        name: str,
        is_valid: bool,
        is_hallucinated: bool = False,
    ) -> None:
        """Record an extracted entity."""
        self.metrics.total_entities_extracted += 1
        if is_valid:
            self.metrics.valid_entities += 1
        if is_hallucinated:
            self.metrics.hallucinated_entities += 1

    def record_summary(self, is_garbled: bool) -> None:
        """Record a generated summary."""
        self.metrics.summaries_generated += 1
        if is_garbled:
            self.metrics.garbled_summaries += 1

    def record_step(self, is_valid: bool) -> None:
        """Record an extracted step."""
        self.metrics.steps_extracted += 1
        if is_valid:
            self.metrics.valid_steps += 1

    def record_duplicate(self) -> None:
        """Record a duplicate detection."""
        self.metrics.duplicates_detected += 1

    def record_error(self, error: str) -> None:
        """Record an error."""
        self.metrics.errors.append(error)

    def finalize_run(self) -> EvalMetrics:
        """Finalize current run and reset for next."""
        self._run_metrics.append(self.metrics)
        self.metrics.log_summary()
        finished = self.metrics
        self.metrics = EvalMetrics()
        return finished

    def get_aggregate(self) -> dict[str, Any]:
        """Get aggregate metrics across all runs."""
        if not self._run_metrics:
            return {}
        total_entities = sum(m.total_entities_extracted for m in self._run_metrics)
        valid_entities = sum(m.valid_entities for m in self._run_metrics)
        hallucinated = sum(m.hallucinated_entities for m in self._run_metrics)
        summaries = sum(m.summaries_generated for m in self._run_metrics)
        garbled = sum(m.garbled_summaries for m in self._run_metrics)
        steps = sum(m.steps_extracted for m in self._run_metrics)
        valid_steps = sum(m.valid_steps for m in self._run_metrics)
        return {
            "runs": len(self._run_metrics),
            "total_entities": total_entities,
            "extraction_precision": valid_entities / total_entities if total_entities else 0,
            "hallucination_rate": hallucinated / total_entities if total_entities else 0,
            "summary_quality": 1.0 - (garbled / summaries if summaries else 0),
            "step_quality": valid_steps / steps if steps else 0,
        }
