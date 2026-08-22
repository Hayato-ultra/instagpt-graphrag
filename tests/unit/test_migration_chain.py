"""Tests for Alembic migration chain integrity (TODO #46).

Verifies all migrations parse correctly, form a valid chain,
and have upgrade/downgrade functions.
"""
import ast
from pathlib import Path
import pytest


MIGRATIONS_DIR = Path("alembic/versions")


def _get_migration_files():
    """Return sorted list of migration files."""
    files = sorted(MIGRATIONS_DIR.glob("0*.py"))
    return files


def _parse_migration(path: Path):
    """Parse a migration file and extract metadata."""
    content = path.read_text()
    tree = ast.parse(content)
    funcs = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    # Extract revision and down_revision via regex
    import re
    revision = None
    down_revision = None
    for line in content.splitlines():
        # Match: revision = '001' or revision: str = '001'
        m = re.match(r"^revision\b.*?=\s*['\"]([^'\"]+)['\"]", line)
        if m:
            revision = m.group(1)
        # Match: down_revision = '002' or down_revision: Union[str, None] = '002'
        if "down_revision" in line and "None" in line:
            down_revision = None
        elif "down_revision" in line:
            m2 = re.search(r"=\s*['\"]([^'\"]+)['\"]", line)
            if m2:
                down_revision = m2.group(1)
    return {
        "file": path.name,
        "revision": revision,
        "down_revision": down_revision,
        "has_upgrade": "upgrade" in funcs,
        "has_downgrade": "downgrade" in funcs,
        "content": content,
    }


class TestMigrationChain:
    """Verify migration chain integrity."""

    def test_all_migrations_parse(self):
        """Every 0*.py in alembic/versions/ parses without error."""
        for f in _get_migration_files():
            _parse_migration(f)  # raises on parse error

    def test_all_migrations_have_upgrade_downgrade(self):
        """Every migration defines upgrade() and downgrade()."""
        for f in _get_migration_files():
            m = _parse_migration(f)
            assert m["has_upgrade"], f"{m['file']} missing upgrade()"
            assert m["has_downgrade"], f"{m['file']} missing downgrade()"

    def test_chain_starts_at_001(self):
        """First migration has down_revision = None."""
        m = _parse_migration(_get_migration_files()[0])
        assert m["revision"] == "001"
        assert m["down_revision"] is None

    def test_chain_links_are_consistent(self):
        """Each migration's down_revision matches the previous migration's revision."""
        files = _get_migration_files()
        migrations = [_parse_migration(f) for f in files]
        for i in range(1, len(migrations)):
            current = migrations[i]
            previous = migrations[i - 1]
            assert current["down_revision"] == previous["revision"], (
                f"{current['file']} down_revision={current['down_revision']} "
                f"but previous is {previous['revision']}"
            )

    def test_no_duplicate_revisions(self):
        """All revision IDs are unique."""
        files = _get_migration_files()
        revisions = [_parse_migration(f)["revision"] for f in files]
        assert len(revisions) == len(set(revisions)), f"Duplicate revisions: {revisions}"
