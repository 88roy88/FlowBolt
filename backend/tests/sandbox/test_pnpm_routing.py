from pathlib import Path


def test_configure_preview_paths_writes_project_base(sandbox, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    sandbox._configure_preview_paths()

    content = (tmp_path / ".env.local").read_text(encoding="utf-8")
    assert "VITE_BASE=/api/preview/test/proxy/" in content
    assert "VITE_BASE_PATH=/api/preview/test/proxy/" in content
    assert "VITE_API_BASE=" in content
