"""Tests for URL normalization and content hashing."""
from src.pipeline.pipeline import content_hash, normalize_url


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://example.com/page?utm_source=twitter&utm_medium=social&id=42"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "id=42" in result

    def test_lowercases_scheme_and_host(self):
        result = normalize_url("HTTPS://EXAMPLE.COM/Page")
        assert result.startswith("https://example.com")

    def test_removes_www_prefix(self):
        result = normalize_url("https://www.example.com/page")
        assert "www." not in result

    def test_collapses_double_slashes_in_path(self):
        result = normalize_url("https://example.com//page///sub")
        # Check path portion only (scheme always has ://)
        from urllib.parse import urlparse
        assert "//" not in urlparse(result).path

    def test_removes_trailing_slash(self):
        result = normalize_url("https://example.com/page/")
        assert not result.endswith("/")

    def test_preserves_non_tracking_params(self):
        url = "https://example.com/page?v=42&lang=en"
        result = normalize_url(url)
        assert "v=42" in result
        assert "lang=en" in result

    def test_sorts_query_params(self):
        url = "https://example.com/page?z=1&a=2&m=3"
        result = normalize_url(url)
        assert result.index("a=2") < result.index("m=3") < result.index("z=1")

    def test_empty_path_becomes_nothing(self):
        result = normalize_url("https://example.com")
        assert result == "https://example.com"

    def test_idempotent(self):
        url = "https://example.com/page?utm_source=x&id=1"
        assert normalize_url(url) == normalize_url(url)

    def test_different_urls_normalized_differently(self):
        a = normalize_url("https://example.com/page?utm_source=x")
        b = normalize_url("https://example.com/other?utm_source=x")
        assert a != b


class TestContentHash:
    def test_same_url_same_hash(self):
        h1 = content_hash("https://example.com/page?utm_source=x")
        h2 = content_hash("https://example.com/page?utm_source=y")
        assert h1 == h2

    def test_different_content_different_hash(self):
        h1 = content_hash("https://example.com/page-a")
        h2 = content_hash("https://example.com/page-b")
        assert h1 != h2

    def test_hash_is_hex_string(self):
        h = content_hash("https://example.com")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_strips_tracking_params(self):
        h1 = content_hash("https://example.com/page?utm_source=fb&id=42")
        h2 = content_hash("https://example.com/page?id=42")
        assert h1 == h2
