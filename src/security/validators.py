"""Security validators: SSRF protection and prompt injection guards.

TODO #52 (Security Risks), #53 (Prompt Injection from Scraped Content).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from loguru import logger

# --- SSRF Protection (TODO #52) ---

_BLOCKED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "metadata.google.internal", "169.254.169.254",
    "instance-data", "100.100.100.200",
}

_BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "vbscript"}


def is_safe_url(url: str) -> bool:
    """Check if URL is safe to fetch (not SSRF)."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Block non-HTTP schemes
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        return False

    # Only allow http/https
    if parsed.scheme.lower() not in ("http", "https"):
        return False

    # Block private/internal hosts
    hostname = (parsed.hostname or "").lower()
    if hostname in _BLOCKED_HOSTS:
        return False

    # Block IP addresses in private ranges
    return not _is_private_ip(hostname)


def _is_private_ip(hostname: str) -> bool:
    """Check if hostname looks like a private IP."""
    import ipaddress
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False  # Not an IP address, that's fine


def sanitize_url(url: str) -> str | None:
    """Sanitize URL, returns None if unsafe."""
    if not is_safe_url(url):
        logger.warning(f"Blocked unsafe URL: {url}")
        return None
    return url


# --- Prompt Injection Guards (TODO #53) ---

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?prior", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"pretend\s+you\s+are", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"ADMIN\s*:", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> bool:
    """Detect potential prompt injection in scraped content."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning(f"Prompt injection detected: {pattern.pattern}")
            return True
    return False


def sanitize_for_llm(text: str, max_length: int = 10000) -> str:
    """Sanitize text before sending to LLM (TODO #53)."""
    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]

    # Remove potential injection attempts
    for pattern in _INJECTION_PATTERNS:
        text = pattern.sub("[REDACTED]", text)

    return text
