from pathlib import Path

import pytest
from pydantic import ValidationError

from flow44.logic.publish_form import load_publish_form_config

ICON = """'''
<svg viewBox="0 0 24 24"></svg>
'''"""


def _write(tmp_path: Path, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / "publish_form.toml"
    path.write_text(text, encoding=encoding)
    return path


def test_loads_another_file_with_multiline_icon_and_bom(tmp_path: Path):
    path = _write(tmp_path, f'[[app_types]]\nid = "tool"\nname = "כלי"\nicon = {ICON}\n', encoding="utf-8-sig")

    config = load_publish_form_config(path)

    assert config.app_types[0].name == "כלי"
    assert config.app_types[0].icon == '<svg viewBox="0 0 24 24"></svg>'
    assert config.publish_reasons == []


@pytest.mark.parametrize(
    "text",
    [
        "app_types = []",
        f'[[app_types]]\nid = "a"\nname = ""\nicon = {ICON}',
        '[[app_types]]\nid = "a"\nname = "A"\nicon = "not-svg"',
        f'[[app_types]]\nid = "a"\nname = "A"\nicon = {ICON}\n' * 2,
        f'publish_reason = []\n[[app_types]]\nid = "a"\nname = "A"\nicon = {ICON}',
    ],
    ids=["no-types", "empty-name", "icon-not-svg", "duplicate-id", "misspelled-key"],
)
def test_rejects_invalid_config(tmp_path: Path, text: str):
    with pytest.raises(ValidationError):
        load_publish_form_config(_write(tmp_path, text))
