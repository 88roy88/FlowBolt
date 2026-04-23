from __future__ import annotations

import pytest

from flow44.integrations.flapi.models import QuickParams


class TestQuickParamsFromValues:
    def test_scalar_values_wrapped_by_type(self) -> None:
        qp = QuickParams.from_values({"name": "alice", "age": 30, "ratio": 1.5, "active": True})
        assert qp.root == {
            "name": {"String": "alice"},
            "age": {"Int": 30},
            "ratio": {"Double": 1.5},
            "active": {"Boolean": True},
        }

    def test_list_values_keep_element_type_key(self) -> None:
        qp = QuickParams.from_values(
            {
                "personIds": [1, 2, 3],
                "regions": ["North", "South"],
                "flags": [True, False],
            }
        )
        assert qp.root == {
            "personIds": {"Int": [1, 2, 3]},
            "regions": {"String": ["North", "South"]},
            "flags": {"Boolean": [True, False]},
        }

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(TypeError):
            QuickParams.from_values({"bad": {"nope": 1}})  # type: ignore[dict-item]
