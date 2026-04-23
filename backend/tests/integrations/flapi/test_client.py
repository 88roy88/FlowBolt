from flow44.integrations.flapi import FlapiClient


class TestAuthHeader:
    def test_none(self) -> None:
        assert FlapiClient._build_auth_header(None) == {}

    def test_empty(self) -> None:
        assert FlapiClient._build_auth_header("") == {}

    def test_whitespace_only(self) -> None:
        assert FlapiClient._build_auth_header("   ") == {}

    def test_valid_token(self) -> None:
        assert FlapiClient._build_auth_header("Bearer abc") == {"Authorization": "Bearer abc"}

    def test_strips_whitespace(self) -> None:
        assert FlapiClient._build_auth_header("  admin  ") == {"Authorization": "admin"}

    def test_passes_raw_token(self) -> None:
        assert FlapiClient._build_auth_header("raw-token") == {"Authorization": "raw-token"}

    def test_bearer_prefix_preserved(self) -> None:
        assert FlapiClient._build_auth_header("BEARER token") == {"Authorization": "BEARER token"}
