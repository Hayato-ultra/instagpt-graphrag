"""Tests for migration 006 indexes (TODO #50)."""
import ast
from pathlib import Path


class TestMigration006:
    """Verify 006_indexes migration is valid."""

    def test_migration_exists(self):
        """006_indexes.py exists and has upgrade/downgrade functions."""
        path = Path("alembic/versions/006_indexes.py")
        assert path.exists(), "006_indexes.py not found"
        content = path.read_text()
        tree = ast.parse(content)
        func_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        assert "upgrade" in func_names
        assert "downgrade" in func_names

    def test_revision_chain(self):
        """006 points back to 005."""
        path = Path("alembic/versions/006_indexes.py")
        content = path.read_text()
        assert 'down_revision = "005"' in content
