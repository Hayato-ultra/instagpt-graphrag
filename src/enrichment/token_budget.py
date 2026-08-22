"""Token budget management for LLM calls (TODO #54).

Tracks usage and enforces per-task token budgets to control costs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from loguru import logger


class TaskType(str, Enum):
    """LLM task types with different token budgets."""
    EXTRACTION = "extraction"
    SUMMARY = "summary"
    CATEGORIZATION = "categorization"
    VALIDATION = "validation"
    CLASSIFICATION = "classification"


@dataclass
class TokenBudget:
    """Token budget for a task type."""
    max_input_tokens: int
    max_output_tokens: int
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

    @property
    def max_cost(self) -> float:
        """Estimate max cost for this budget."""
        return (
            (self.max_input_tokens / 1000) * self.cost_per_1k_input
            + (self.max_output_tokens / 1000) * self.cost_per_1k_output
        )


# Default budgets per task type
DEFAULT_BUDGETS = {
    TaskType.EXTRACTION: TokenBudget(
        max_input_tokens=12000,
        max_output_tokens=4000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    TaskType.SUMMARY: TokenBudget(
        max_input_tokens=16000,
        max_output_tokens=2000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    TaskType.CATEGORIZATION: TokenBudget(
        max_input_tokens=4000,
        max_output_tokens=1000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    TaskType.VALIDATION: TokenBudget(
        max_input_tokens=8000,
        max_output_tokens=1000,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
    TaskType.CLASSIFICATION: TokenBudget(
        max_input_tokens=2000,
        max_output_tokens=500,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006,
    ),
}


@dataclass
class UsageTracker:
    """Track token usage across tasks."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    calls: int = 0

    def record(
        self,
        input_tokens: int,
        output_tokens: int,
        cost_per_1k_input: float,
        cost_per_1k_output: float,
    ) -> None:
        """Record a single API call's usage."""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        cost = (
            (input_tokens / 1000) * cost_per_1k_input
            + (output_tokens / 1000) * cost_per_1k_output
        )
        self.total_cost += cost
        self.calls += 1

    def summary(self) -> dict:
        """Get usage summary."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": round(self.total_cost, 6),
            "calls": self.calls,
            "avg_tokens_per_call": (
                (self.total_input_tokens + self.total_output_tokens) // max(self.calls, 1)
            ),
        }


class TokenBudgetManager:
    """Manage token budgets and track usage (TODO #54)."""

    def __init__(self, budgets: dict[TaskType, TokenBudget] | None = None):
        self.budgets = budgets or DEFAULT_BUDGETS
        self.tracker = UsageTracker()

    def get_budget(self, task_type: TaskType) -> TokenBudget:
        """Get budget for a task type."""
        return self.budgets.get(task_type, DEFAULT_BUDGETS[TaskType.EXTRACTION])

    def check_budget(
        self,
        task_type: TaskType,
        estimated_input_tokens: int,
    ) -> bool:
        """Check if estimated tokens fit within budget."""
        budget = self.get_budget(task_type)
        fits = estimated_input_tokens <= budget.max_input_tokens
        if not fits:
            logger.warning(
                f"Token budget exceeded for {task_type}: "
                f"{estimated_input_tokens} > {budget.max_input_tokens}"
            )
        return fits

    def record_usage(
        self,
        task_type: TaskType,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record usage for a task type."""
        budget = self.get_budget(task_type)
        self.tracker.record(
            input_tokens,
            output_tokens,
            budget.cost_per_1k_input,
            budget.cost_per_1k_output,
        )

    def should_use_fallback(self, task_type: TaskType) -> bool:
        """Determine if fallback model should be used based on budget."""
        budget = self.get_budget(task_type)
        # Use fallback for expensive tasks if cost is high
        return self.tracker.total_cost > 0.5 and budget.max_cost > 0.01

    def get_routing_recommendation(self, task_type: TaskType) -> str:
        """Recommend primary or fallback model based on budget."""
        if self.should_use_fallback(task_type):
            return "fallback"
        return "primary"
