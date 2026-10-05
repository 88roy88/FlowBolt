from unittest.mock import AsyncMock, patch

import pytest

from flow44.sandbox.operations import build_dist


@pytest.mark.asyncio
async def test_build_dist_returns_posix_keys_for_nested_files(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_bytes(b"<html></html>")
    (dist / "assets" / "app.js").write_bytes(b"x")

    with patch("flow44.sandbox.operations._build_dist_dir", AsyncMock(return_value=str(dist))):
        files = dict(await build_dist("proj-1"))

    assert set(files) == {"index.html", "assets/app.js"}
    assert files["assets/app.js"] == b"x"
