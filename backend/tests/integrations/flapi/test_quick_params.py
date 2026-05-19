from __future__ import annotations

from flow44.integrations.flapi.models import QuickParams


class TestQuickParams:
    def test_grouped_by_cube_id(self) -> None:
        qp = QuickParams(root={
            "cube-1": {"name": "alice", "age": 30},
            "cube-2": {"active": True},
        })
        assert qp.root == {
            "cube-1": {"name": "alice", "age": 30},
            "cube-2": {"active": True},
        }

    def test_empty(self) -> None:
        qp = QuickParams(root={})
        assert qp.root == {}

    def test_list_values(self) -> None:
        qp = QuickParams(root={
            "cube-1": {"personIds": [1, 2, 3], "regions": ["North", "South"]},
        })
        assert qp.root == {
            "cube-1": {"personIds": [1, 2, 3], "regions": ["North", "South"]},
        }
