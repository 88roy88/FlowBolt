from __future__ import annotations

from flow44.integrations.flapi.models import QuickParams


class TestQuickParamsFromValues:
    def test_scalar_values_wrapped_in_default_group(self) -> None:
        qp = QuickParams.from_values({"name": "alice", "age": 30, "ratio": 1.5, "active": True})
        assert qp.root == {
            "default": { #This is queryId
                "name": [{"Value": "alice", "Name": "alice"}],
                "age": [{"Value": 30, "Name": 30}],
                "ratio": [{"Value": 1.5, "Name": 1.5}],
                "active": [{"Value": True, "Name": True}],
            }
        }

    def test_list_values_expanded_into_value_name_dicts(self) -> None:
        qp = QuickParams.from_values(
            {
                "personIds": [1, 2, 3],
                "regions": ["North", "South"],
                "flags": [True, False],
            }
        )
        assert qp.root == {
            "default": {
                "personIds": [{"Value": 1, "Name": 1}, {"Value": 2, "Name": 2}, {"Value": 3, "Name": 3}],
                "regions": [{"Value": "North", "Name": "North"}, {"Value": "South", "Name": "South"}],
                "flags": [{"Value": True, "Name": True}, {"Value": False, "Name": False}],
            }
        }

    def test_info_groups_params_by_group_key(self) -> None:
        from flow44.integrations.flapi.models import QuickParamsInfo

        info = QuickParamsInfo.model_validate({
            "groupA": [{"Name": "name", "DisplayName": "Name", "Type": "String",
                        "IsSingleValue": True, "IsRequired": True, "IsRequireAny": False, "Value": []}],
            "groupB": [{"Name": "age", "DisplayName": "Age", "Type": "Int",
                        "IsSingleValue": True, "IsRequired": False, "IsRequireAny": False, "Value": []}],
        })
        qp = QuickParams.from_values({"name": "alice", "age": 30}, info=info)
        assert qp.root == {
            "groupA": {"name": [{"Value": "alice", "Name": "alice"}]},
            "groupB": {"age": [{"Value": 30, "Name": 30}]},
        }
