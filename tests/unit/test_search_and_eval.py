"""Tests for adaptive search weighting (TODO #37) and evaluation framework (TODO #38)."""
from src.search import _classify_query, HybridSearcher
from src.enrichment.evaluator import PipelineEvaluator, EvalMetrics


class TestQueryClassification:
    """TODO #37: Adaptive search weighting."""

    def test_lookup_query(self):
        assert _classify_query("React") == "lookup"
        assert _classify_query("Docker") == "lookup"

    def test_semantic_query(self):
        assert _classify_query("similar to React") == "semantic"
        assert _classify_query("what is this about") == "semantic"

    def test_relationship_query(self):
        assert _classify_query("what depends on Docker") == "relationship"
        assert _classify_query("who calls this function") == "relationship"

    def test_balanced_query(self):
        assert _classify_query("how to build a web app") == "balanced"


class TestEvalMetrics:
    """TODO #38: Evaluation metrics."""

    def test_empty_metrics(self):
        m = EvalMetrics()
        assert m.extraction_precision == 0.0
        assert m.hallucination_rate == 0.0
        assert m.summary_quality == 0.0
        assert m.step_quality == 0.0

    def test_precision_calculation(self):
        m = EvalMetrics(total_entities_extracted=10, valid_entities=8)
        assert m.extraction_precision == 0.8

    def test_hallucination_rate(self):
        m = EvalMetrics(total_entities_extracted=10, hallucinated_entities=3)
        assert m.hallucination_rate == 0.3

    def test_summary_quality(self):
        m = EvalMetrics(summaries_generated=5, garbled_summaries=1)
        assert m.summary_quality == 0.8

    def test_to_dict(self):
        m = EvalMetrics(total_entities_extracted=5, valid_entities=4)
        d = m.to_dict()
        assert d["extraction_precision"] == 0.8
        assert "hallucination_rate" in d


class TestPipelineEvaluator:
    """TODO #38: Pipeline evaluator."""

    def test_record_entity(self):
        e = PipelineEvaluator()
        e.record_entity("Docker", is_valid=True)
        e.record_entity("Kubernetes", is_valid=False, is_hallucinated=True)
        assert e.metrics.total_entities_extracted == 2
        assert e.metrics.valid_entities == 1
        assert e.metrics.hallucinated_entities == 1

    def test_finalize_and_aggregate(self):
        e = PipelineEvaluator()
        e.record_entity("Docker", is_valid=True)
        e.record_entity("Fake", is_valid=False, is_hallucinated=True)
        finished = e.finalize_run()
        assert finished.total_entities_extracted == 2
        agg = e.get_aggregate()
        assert agg["runs"] == 1
        assert agg["extraction_precision"] == 0.5
