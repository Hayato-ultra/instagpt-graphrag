"""Tests for post-extraction validation (TODO #2, #3, #6, #10, #27)."""
from src.enrichment.post_validation import (
    validate_entity_name,
    validate_confidence,
    post_validate_entities,
    _is_ocr_noise,
    _fix_misspelling,
)


class TestOCRNoise:
    """TODO #27: OCR noise detection."""

    def test_follow_this_detected(self):
        assert _is_ocr_noise("Follow this for more")

    def test_likes_count_detected(self):
        assert _is_ocr_noise("10k likes")

    def test_clean_text_passes(self):
        assert not _is_ocr_noise("Docker is a container platform")


class TestMisspellingFix:
    """TODO #10: Entity name misspelling."""

    def test_known_fix(self):
        assert _fix_misspelling("Apprite") == "appwrite"

    def test_unknown_kept(self):
        assert _fix_misspelling("Docker") == "Docker"

    def test_reactjs_fix(self):
        assert _fix_misspelling("ReactJS") == "react"


class TestEntityNameValidation:
    """TODO #2, #3: Hallucination and URL error filtering."""

    def test_valid_name(self):
        assert validate_entity_name("Docker") == "Docker"

    def test_empty_name(self):
        assert validate_entity_name("") is None

    def test_short_name(self):
        assert validate_entity_name("A") is None

    def test_platform_filtered(self):
        assert validate_entity_name("Instagram") is None
        assert validate_entity_name("YouTube") is None

    def test_generic_filtered(self):
        assert validate_entity_name("website") is None
        assert validate_entity_name("animations") is None

    def test_numeric_filtered(self):
        assert validate_entity_name("48 chimneys") is None

    def test_misspelling_fixed(self):
        assert validate_entity_name("Apprite") == "appwrite"

    def test_ocr_noise_filtered(self):
        assert validate_entity_name("Follow this for more") is None


class TestConfidenceValidation:
    """TODO #6: 0% confidence auto-rejection."""

    def test_high_confidence_passes(self):
        assert validate_confidence({"confidence": 0.9})

    def test_low_confidence_rejected(self):
        assert not validate_confidence({"confidence": 0.1})

    def test_zero_confidence_rejected(self):
        assert not validate_confidence({"confidence": 0.0})


class TestPostValidation:
    """Full post-validation pipeline."""

    def test_filters_invalid(self):
        entities = [
            {"name": "Docker", "confidence": 0.9},
            {"name": "Instagram", "confidence": 0.8},
            {"name": "", "confidence": 0.7},
        ]
        result = post_validate_entities(entities)
        assert len(result) == 1
        assert result[0]["name"] == "Docker"

    def test_dedup(self):
        entities = [
            {"name": "Docker", "confidence": 0.9},
            {"name": "docker", "confidence": 0.8},
        ]
        result = post_validate_entities(entities)
        assert len(result) == 1

    def test_fixes_misspellings(self):
        entities = [{"name": "Apprite", "confidence": 0.9}]
        result = post_validate_entities(entities)
        assert result[0]["name"] == "appwrite"
