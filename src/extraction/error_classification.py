"""Web scraping error classification (TODO #41).

Classifies errors as temporary, permanent, or auth-related for retry logic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from loguru import logger


class ErrorType(str, Enum):
    """Classification of web scraping errors."""
    TEMPORARY = "temporary"      # Rate limit, timeout, 5xx → retry
    PERMANENT = "permanent"      # 404, invalid URL, content removed → don't retry
    AUTH = "auth"                # 401, 403, login required → need credentials
    NETWORK = "network"          # DNS, connection refused → retry with backoff
    UNKNOWN = "unknown"          # Unclassified


@dataclass
class ClassifiedError:
    """Error with classification and retry guidance."""
    error_type: ErrorType
    message: str
    should_retry: bool
    retry_after: float | None = None  # seconds
    status_code: int | None = None


# Status code classification
_TEMPORARY_STATUS = {408, 429, 500, 502, 503, 504}
_PERMANENT_STATUS = {400, 404, 410, 422}
_AUTH_STATUS = {401, 403, 407}

# Error message patterns
_TEMPORARY_PATTERNS = [
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"rate.?limit", re.IGNORECASE),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"service unavailable", re.IGNORECASE),
    re.compile(r"gateway error", re.IGNORECASE),
]

_AUTH_PATTERNS = [
    re.compile(r"unauthorized", re.IGNORECASE),
    re.compile(r"forbidden", re.IGNORECASE),
    re.compile(r"login required", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
    re.compile(r"sign.?in", re.IGNORECASE),
]

_NETWORK_PATTERNS = [
    re.compile(r"connection refused", re.IGNORECASE),
    re.compile(r"dns", re.IGNORECASE),
    re.compile(r"network unreachable", re.IGNORECASE),
    re.compile(r"name or service not known", re.IGNORECASE),
]


def classify_error(
    error: Exception,
    status_code: int | None = None,
) -> ClassifiedError:
    """Classify a web scraping error for retry logic (TODO #41).

    Args:
        error: the exception that occurred.
        status_code: optional HTTP status code.

    Returns:
        ClassifiedError with type and retry guidance.
    """
    msg = str(error)

    # Check status code first
    if status_code:
        if status_code in _TEMPORARY_STATUS:
            retry_after = 60.0 if status_code == 429 else 30.0
            return ClassifiedError(
                error_type=ErrorType.TEMPORARY,
                message=f"HTTP {status_code}",
                should_retry=True,
                retry_after=retry_after,
                status_code=status_code,
            )
        if status_code in _PERMANENT_STATUS:
            return ClassifiedError(
                error_type=ErrorType.PERMANENT,
                message=f"HTTP {status_code}",
                should_retry=False,
                status_code=status_code,
            )
        if status_code in _AUTH_STATUS:
            return ClassifiedError(
                error_type=ErrorType.AUTH,
                message=f"HTTP {status_code}",
                should_retry=False,
                status_code=status_code,
            )

    # Check error message patterns
    for pattern in _TEMPORARY_PATTERNS:
        if pattern.search(msg):
            return ClassifiedError(
                error_type=ErrorType.TEMPORARY,
                message=msg[:200],
                should_retry=True,
                retry_after=30.0,
            )

    for pattern in _AUTH_PATTERNS:
        if pattern.search(msg):
            return ClassifiedError(
                error_type=ErrorType.AUTH,
                message=msg[:200],
                should_retry=False,
            )

    for pattern in _NETWORK_PATTERNS:
        if pattern.search(msg):
            return ClassifiedError(
                error_type=ErrorType.NETWORK,
                message=msg[:200],
                should_retry=True,
                retry_after=60.0,
            )

    return ClassifiedError(
        error_type=ErrorType.UNKNOWN,
        message=msg[:200],
        should_retry=True,  # Default to retry for unknown errors
    )
