from flow44.api.preview import _TOOLBAR_FILE, _TOOLBAR_TAG, _inject_toolbar


def test_injects_before_head_close() -> None:
    html = b"<html><head><title>x</title></head><body></body></html>"
    assert _inject_toolbar(html) == b"<html><head><title>x</title>" + _TOOLBAR_TAG + b"</head><body></body></html>"


def test_falls_back_to_body_close_case_insensitively() -> None:
    html = b"<div>app</div></BODY>"
    assert _inject_toolbar(html) == b"<div>app</div>" + _TOOLBAR_TAG + b"</BODY>"


def test_appends_when_no_markers() -> None:
    assert _inject_toolbar(b"<div>app</div>") == b"<div>app</div>" + _TOOLBAR_TAG


def test_toolbar_script_ships_with_the_package() -> None:
    assert _TOOLBAR_FILE.is_file()
