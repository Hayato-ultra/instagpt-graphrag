"""Tests for data consistency checker (TODO #33)."""
from src.database.consistency import ConsistencyReport, ConsistencyIssue


class TestConsistencyReport:
    """TODO #33: Data consistency reporting."""

    def test_empty_report(self):
        r = ConsistencyReport()
        assert r.consistency_rate == 1.0

    def test_consistency_rate(self):
        r = ConsistencyReport(total_entities=10, consistent=8)
        assert r.consistency_rate == 0.8

    def test_issues_list(self):
        r = ConsistencyReport()
        r.issues.append(ConsistencyIssue(
            entity_id="1", entity_name="Docker",
            issue_type="missing_neo4j", details="Missing"
        ))
        assert len(r.issues) == 1
        assert r.issues[0].severity == "warning"
