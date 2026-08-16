"""Tests for FileDiff computation and the run-level DiffTracker."""

from __future__ import annotations

from flow44.ai.agents.file_diffs import DiffTracker


class TestDiffTracker:
    def test_single_write(self) -> None:
        tracker = DiffTracker()
        tracker.record("src/App.tsx", "old\n", "new\n", is_new=False)

        diffs = tracker.combined_diffs()
        assert len(diffs) == 1
        assert diffs[0].path == "src/App.tsx"
        assert diffs[0].is_new is False
        assert "-old" in diffs[0].diff
        assert "+new" in diffs[0].diff

    def test_repeat_writes_combine_into_one_diff(self) -> None:
        tracker = DiffTracker()
        tracker.record("src/App.tsx", "v1\n", "v2\n", is_new=False)
        tracker.record("src/App.tsx", "v2\n", "v3\n", is_new=False)

        diffs = tracker.combined_diffs()
        assert len(diffs) == 1
        # Combined diff goes straight from original to final; the interim v2 never appears.
        assert "-v1" in diffs[0].diff
        assert "+v3" in diffs[0].diff
        assert "v2" not in diffs[0].diff

    def test_reverted_change_is_dropped(self) -> None:
        tracker = DiffTracker()
        tracker.record("src/App.tsx", "orig\n", "changed\n", is_new=False)
        tracker.record("src/App.tsx", "changed\n", "orig\n", is_new=False)

        assert tracker.combined_diffs() == []

    def test_new_file_then_edit_stays_new(self) -> None:
        tracker = DiffTracker()
        tracker.record("src/New.tsx", "", "v1\n", is_new=True)
        tracker.record("src/New.tsx", "v1\n", "v2\n", is_new=False)

        diffs = tracker.combined_diffs()
        assert len(diffs) == 1
        assert diffs[0].is_new is True
        assert "+v2" in diffs[0].diff

    def test_multiple_files_get_separate_diffs(self) -> None:
        tracker = DiffTracker()
        tracker.record("src/A.tsx", "a1\n", "a2\n", is_new=False)
        tracker.record("src/B.tsx", "", "b1\n", is_new=True)

        diffs = {d.path: d for d in tracker.combined_diffs()}
        assert set(diffs) == {"src/A.tsx", "src/B.tsx"}
        assert diffs["src/A.tsx"].is_new is False
        assert diffs["src/B.tsx"].is_new is True

    def test_empty_tracker_yields_no_diffs(self) -> None:
        assert DiffTracker().combined_diffs() == []
