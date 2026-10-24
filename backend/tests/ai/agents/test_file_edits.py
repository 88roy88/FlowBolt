"""Tests for the shared search/replace edit helper."""

from __future__ import annotations

import pytest

from flow44.ai.agents.fix_error.file_edits import EditApplyError, apply_edits


def test_applies_pairs_in_order() -> None:
    assert apply_edits("a b c", [("a", "x"), ("x b", "y")]) == "y c"


def test_rejects_missing_search() -> None:
    with pytest.raises(EditApplyError, match="the search string was not found"):
        apply_edits("hello world", [("NOPE", "x")])


def test_rejects_ambiguous_search() -> None:
    with pytest.raises(EditApplyError, match="matches 2 places"):
        apply_edits("x\nx\n", [("x", "y")])


def test_rejects_empty_search() -> None:
    with pytest.raises(EditApplyError, match="not found"):
        apply_edits("x", [("", "y")])


def test_rejects_no_pairs() -> None:
    with pytest.raises(EditApplyError, match="no search/replace pairs"):
        apply_edits("x", [])
