"""Hallucination detection: validate extracted entities against source transcript.

TODO #12, #13, #14, #15 — detect fabricated entities, misspellings, missing entities.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from loguru import logger


@dataclass
class ValidationResult:
    """Result of hallucination check."""
    valid: list[str] = field(default_factory=list)
    suspected: list[str] = field(default_factory=list)
    misspelled: list[tuple[str, str]] = field(default_factory=list)  # (extracted, closest_in_text)
    missing: list[str] = field(default_factory=list)
    confidence: float = 1.0

    @property
    def has_issues(self) -> bool:
        return bool(self.suspected or self.misspelled or self.missing)


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _fuzzy_match(name: str, text: str, threshold: float = 0.6) -> str | None:
    """Find the best fuzzy match of name in text. Returns match or None."""
    name_lower = _normalize(name)
    words = _normalize(text).split()

    # Check single words
    for word in words:
        if SequenceMatcher(None, name_lower, word).ratio() >= threshold:
            return word

    # Check multi-word substrings
    for i in range(len(words)):
        for j in range(i + 1, min(i + 4, len(words) + 1)):
            phrase = " ".join(words[i:j])
            if SequenceMatcher(None, name_lower, phrase).ratio() >= threshold:
                return phrase

    return None


def _contains_exact(name: str, text: str) -> bool:
    """Check if name appears in text (case-insensitive)."""
    return name.lower() in text.lower()


def validate_entities(
    entity_names: list[str],
    source_text: str,
    known_aliases: dict[str, list[str]] | None = None,
) -> ValidationResult:
    """Validate extracted entity names against source transcript.

    Args:
        entity_names: list of extracted entity names.
        source_text: the original transcript/caption text.
        known_aliases: optional dict mapping canonical names to aliases.

    Returns:
        ValidationResult with valid/suspected/misspelled/missing lists.
    """
    result = ValidationResult()
    aliases = known_aliases or {}

    # Build alias lookup (alias → canonical)
    alias_to_canonical = {}
    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            alias_to_canonical[alias.lower()] = canonical

    for name in entity_names:
        # 1. Exact match in text
        if _contains_exact(name, source_text):
            result.valid.append(name)
            continue

        # 2. Check aliases
        canonical = alias_to_canonical.get(name.lower())
        if canonical and _contains_exact(canonical, source_text):
            result.valid.append(name)
            continue

        # 3. Fuzzy match
        match = _fuzzy_match(name, source_text, threshold=0.75)
        if match:
            # Close enough — likely a misspelling or transcription variant
            result.misspelled.append((name, match))
            result.valid.append(name)
            continue

        # 4. Weak fuzzy match — suspect hallucination
        weak_match = _fuzzy_match(name, source_text, threshold=0.5)
        if weak_match:
            result.suspected.append(name)
            continue

        # 5. No match at all — likely hallucinated
        result.suspected.append(name)

    # Calculate confidence
    total = len(entity_names) if entity_names else 1
    result.confidence = len(result.valid) / total

    if result.suspected:
        logger.warning(
            f"Hallucination check: {len(result.suspected)} suspected entities: "
            f"{result.suspected}"
        )
    if result.misspelled:
        logger.info(
            f"Hallucination check: {len(result.misspelled)} misspelled: "
            f"{result.misspelled}"
        )

    return result


def filter_hallucinated(
    entities: list[dict],
    source_text: str,
    confidence_threshold: float = 0.5,
) -> list[dict]:
    """Filter out suspected hallucinated entities.

    Args:
        entities: list of entity dicts with 'name', 'confidence', etc.
        source_text: the original transcript.
        confidence_threshold: minimum confidence to keep.

    Returns:
        Filtered list of entities.
    """
    names = [e.get("name", "") for e in entities]
    validation = validate_entities(names, source_text)

    filtered = []
    for entity, is_valid in zip(entities, [n in validation.valid for n in names]):
        if is_valid and entity.get("confidence", 0) >= confidence_threshold:
            filtered.append(entity)
        else:
            name = entity.get("name")
            conf = entity.get("confidence", 0)
            logger.debug(f"Filtered entity '{name}' (valid={is_valid}, conf={conf:.2f})")

    logger.info(f"Hallucination filter: {len(entities)} → {len(filtered)} entities")
    return filtered
