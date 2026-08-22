"""Tests for output quality validators (TODO #4, #5, #17, #18) and graph cleanup (#35)."""


class TestTemplateDescriptionValidation:
    """TODO #4: Reject template descriptions like 'EntityType.X in the source content'."""

    def test_detects_entity_type_template(self):
        from src.enrichment.enrichment import is_template_description

        assert is_template_description("docker is a EntityType.PLATFORM in the source content")
        assert is_template_description("aws is a EntityType.TOOL")
        assert is_template_description("This is EntityType.UNKNOWN")

    def test_accepts_real_description(self):
        from src.enrichment.enrichment import is_template_description

        assert not is_template_description("Docker is a containerization platform")
        assert not is_template_description("React is a JavaScript UI library")
        assert not is_template_description("")

    def test_clears_template_in_validation(self):
        from src.enrichment.enrichment import is_template_description

        desc = "vscode is a EntityType.TOOL in the source content"
        assert is_template_description(desc)


class TestSummaryEntityTypeValidation:
    """TODO #5: Reject summaries containing EntityType keywords."""

    def test_detects_entity_type_in_summary(self):
        from src.enrichment.enrichment import is_template_summary

        assert is_template_summary("web app is a EntityType.WEB_APP")
        assert is_template_summary("docker is a EntityType.PLATFORM")

    def test_accepts_real_summary(self):
        from src.enrichment.enrichment import is_template_summary

        assert not is_template_summary("This tutorial covers Docker containerization basics")
        assert not is_template_summary("")


class TestSeriesNameFilter:
    """TODO #17: Filter series/channel intro phrases."""

    def test_detects_series_names(self):
        from src.enrichment.enrichment import is_series_name

        assert is_series_name("Day 9 of making you financially independent")
        assert is_series_name("Episode 5 of Learning React")
        assert is_series_name("Part 3 of 10: Advanced CSS")

    def test_accepts_normal_names(self):
        from src.enrichment.enrichment import is_series_name

        assert not is_series_name("Docker")
        assert not is_series_name("Financial Freedom Course")


class TestEntityTypeSkip:
    """TODO #18: Skip languages/frameworks as standalone entities."""

    def test_skips_language_type(self):
        from src.config.models import EntityType
        from src.enrichment.enrichment import should_skip_entity_type

        assert should_skip_entity_type(EntityType.LANGUAGE)

    def test_does_not_skip_tool_type(self):
        from src.config.models import EntityType
        from src.enrichment.enrichment import should_skip_entity_type

        assert not should_skip_entity_type(EntityType.TOOL)
        assert not should_skip_entity_type(EntityType.PLATFORM)


class TestGraphCleanup:
    """TODO #35: Graph cleanup job flags stale/low-confidence/isolated nodes."""

    def test_cleanup_result_dataclass(self):
        from src.database.cleanup import CleanupResult

        r = CleanupResult()
        assert r.low_confidence == 0
        assert r.stale == 0
        assert r.isolated == 0
        assert r.flagged == []
