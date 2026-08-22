"""Schema evolution tests (TODO #46).

Tests that verify schema changes don't break existing data.
"""
from __future__ import annotations

import pytest


class TestSchemaEvolution:
    """TODO #46: Schema evolution across multiple systems."""

    def test_entity_model_has_required_columns(self):
        """Verify Entity model has all required columns."""
        from src.database.models import Entity
        columns = [c.name for c in Entity.__table__.columns]

        # Core fields
        assert "id" in columns
        assert "name" in columns
        assert "entity_type_id" in columns
        assert "description" in columns
        assert "confidence" in columns

        # Provenance fields
        assert "pipeline_version" in columns
        assert "model_version" in columns
        assert "embedding_version" in columns

        # Temporal fields (TODO #57)
        assert "valid_from" in columns
        assert "valid_until" in columns

    def test_outbox_event_types_complete(self):
        """Verify all outbox event types are defined."""
        from src.database.models import OutboxEventType
        required_types = [
            "ENTITY_UPSERT",
            "ENTITY_DELETE",
            "RELATIONSHIP_UPSERT",
            "CONTENT_CHUNKS_UPSERT",
            "CONTENT_DELETE",
        ]
        for rt in required_types:
            assert hasattr(OutboxEventType, rt), f"Missing {rt}"

    def test_entity_type_enum_complete(self):
        """Verify EntityType enum has all required types."""
        from src.database.models import EntityType
        required_types = [
            "WEB_APP", "MOBILE_APP", "TOOL", "FRAMEWORK", "LIBRARY",
            "PLATFORM", "SERVICE", "API", "DATABASE", "CONCEPT",
            "RELATED", "UNKNOWN",
        ]
        for rt in required_types:
            assert hasattr(EntityType, rt), f"Missing {rt}"

    def test_pipeline_versions_dataclass(self):
        """Verify PipelineVersions has all version fields."""
        from src.pipeline.versions import PipelineVersions
        v = PipelineVersions()
        assert hasattr(v, "pipeline_version")
        assert hasattr(v, "model_version")
        assert hasattr(v, "prompt_version")
        assert hasattr(v, "embedding_version")
        assert hasattr(v, "schema_version")
