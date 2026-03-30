"""Tests for sandbox HTML inlining helpers in operations.py.

All functions tested here are pure (read files + transform strings) — no sandbox needed.
"""

import base64

import pytest

from flow44.sandbox.operations import (
    _inline_css_assets,
    _inline_favicon,
    _inline_js_assets,
    _resolve_asset_path,
)


class TestResolveAssetPath:
    def test_valid_relative_path(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        result = _resolve_asset_path(str(dist), "/assets/main.js")
        assert result is not None
        assert result.endswith("main.js")

    def test_traversal_returns_none(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        result = _resolve_asset_path(str(dist), "../../etc/passwd")
        assert result is None

    def test_nested_valid_path(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        (dist / "assets").mkdir(parents=True)
        result = _resolve_asset_path(str(dist), "/assets/chunk.js")
        assert result is not None
        assert "chunk.js" in result


class TestInlineCssAssets:
    def test_inlines_stylesheet(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "style.css").write_text("body { color: red; }")

        html = '<link rel="stylesheet" href="/style.css">'
        result = _inline_css_assets(html, str(dist))

        assert "<style>" in result
        assert "color: red" in result
        assert '<link' not in result

    def test_inlines_stylesheet_href_first(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "style.css").write_text("h1 { font-size: 2rem; }")

        html = '<link href="/style.css" rel="stylesheet">'
        result = _inline_css_assets(html, str(dist))

        assert "<style>" in result
        assert "2rem" in result

    def test_missing_file_leaves_tag_unchanged(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        html = '<link rel="stylesheet" href="/missing.css">'
        result = _inline_css_assets(html, str(dist))
        assert '<link' in result  # unchanged

    def test_non_stylesheet_link_untouched(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        html = '<link rel="icon" href="/favicon.ico">'
        result = _inline_css_assets(html, str(dist))
        assert '<link rel="icon"' in result


class TestInlineJsAssets:
    def test_inlines_script(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "main.js").write_text("console.log('hi')")

        html = '<script src="/main.js"></script>'
        result = _inline_js_assets(html, str(dist))

        assert "<script>" in result or "<script " in result
        assert "console.log" in result
        assert 'src=' not in result

    def test_preserves_type_attribute(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "mod.js").write_text("export default 1")

        html = '<script type="module" src="/mod.js"></script>'
        result = _inline_js_assets(html, str(dist))

        assert 'type="module"' in result
        assert "export default 1" in result

    def test_missing_file_leaves_tag_unchanged(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        html = '<script src="/missing.js"></script>'
        result = _inline_js_assets(html, str(dist))
        assert 'src=' in result  # unchanged


class TestInlineFavicon:
    def test_inlines_png_favicon(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        favicon_data = b"\x89PNG\r\n\x1a\n"  # minimal PNG header
        (dist / "favicon.png").write_bytes(favicon_data)

        html = '<link rel="icon" href="/favicon.png">'
        result = _inline_favicon(html, str(dist), str(tmp_path))

        assert "data:image/png;base64," in result
        expected_b64 = base64.b64encode(favicon_data).decode()
        assert expected_b64 in result

    def test_inlines_svg_favicon(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        svg_data = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
        (dist / "icon.svg").write_bytes(svg_data)

        html = '<link rel="icon" href="/icon.svg">'
        result = _inline_favicon(html, str(dist), str(tmp_path))

        assert "data:image/svg+xml;base64," in result

    def test_missing_favicon_leaves_tag_unchanged(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        html = '<link rel="icon" href="/missing.ico">'
        result = _inline_favicon(html, str(dist), str(tmp_path))
        assert '<link rel="icon"' in result

    def test_shortcut_icon_rel(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "fav.ico").write_bytes(b"ICO")

        html = '<link rel="shortcut icon" href="/fav.ico">'
        result = _inline_favicon(html, str(dist), str(tmp_path))

        assert "data:" in result

    def test_falls_back_to_workspace_public(self, tmp_path) -> None:  # type: ignore[type-arg]
        dist = tmp_path / "dist"
        dist.mkdir()
        public = tmp_path / "public"
        public.mkdir()
        (public / "logo.png").write_bytes(b"PNG")

        html = '<link rel="icon" href="/logo.png">'
        result = _inline_favicon(html, str(dist), str(tmp_path))

        assert "data:image/png;base64," in result
