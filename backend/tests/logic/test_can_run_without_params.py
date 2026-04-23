"""Tests for can_run_without_params logic."""

from __future__ import annotations

import pytest

from flow44.logic import data_source as ds_logic
from flow44.logic.models import DataSourceParamsInfo, ParamDefinition, ParamOption


class TestCanRunWithoutParams:
    """Test the can_run_without_params function."""

    async def test_no_params_can_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with no params can run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(parameters=[], require_any=False)

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {}  # Empty dict since no params needed

    async def test_all_optional_params_can_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with only optional params can run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="category",
                        display_name="Category",
                        type="String",
                        is_required=False,
                        is_single_value=False,
                        options=[ParamOption(name="Electronics", value="Electronics")],
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {}  # Empty dict since all params are optional

    async def test_required_param_with_default_can_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with required param that has default value can run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="status",
                        display_name="Status",
                        type="String",
                        is_required=True,
                        is_single_value=False,
                        options=[
                            ParamOption(name="Active", value="Active"),
                            ParamOption(name="Inactive", value="Inactive"),
                        ],
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {"status": "Active"}  # Uses first option as default

    async def test_required_param_without_options_cannot_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with required param but no default values cannot run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="user_id",
                        display_name="User ID",
                        type="Integer",
                        is_required=True,
                        is_single_value=True,
                        options=[],  # No options = no default
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is False
        assert params is None

    async def test_mixed_params_with_defaults_can_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with mix of optional and required (with defaults) can run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="status",
                        display_name="Status",
                        type="String",
                        is_required=True,
                        is_single_value=False,
                        options=[ParamOption(name="Active", value="Active")],
                    ),
                    ParamDefinition(
                        name="category",
                        display_name="Category",
                        type="String",
                        is_required=False,
                        is_single_value=False,
                        options=[ParamOption(name="All", value="All")],
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {"status": "Active"}  # Only required param included

    async def test_integer_param_converted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Integer type params are converted to int."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="limit",
                        display_name="Limit",
                        type="Integer",
                        is_required=True,
                        is_single_value=True,
                        options=[ParamOption(name="100", value="100")],
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {"limit": 100}
        assert isinstance(params.root["limit"], int)

    async def test_boolean_param_converted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Boolean type params are converted to bool."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="active",
                        display_name="Active",
                        type="Boolean",
                        is_required=True,
                        is_single_value=True,
                        options=[ParamOption(name="Yes", value="true")],
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {"active": True}
        assert isinstance(params.root["active"], bool)

    async def test_invalid_integer_cannot_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If integer param value cannot be parsed, cannot run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="count",
                        display_name="Count",
                        type="Integer",
                        is_required=True,
                        is_single_value=True,
                        options=[ParamOption(name="Invalid", value="not-a-number")],
                    ),
                ],
                require_any=False,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is False
        assert params is None

    async def test_require_any_with_defaults_can_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with RequireAny where at least one has default can run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="filter1",
                        display_name="Filter 1",
                        type="String",
                        is_required=False,
                        is_single_value=False,
                        is_require_any=True,
                        options=[ParamOption(name="A", value="A")],
                    ),
                    ParamDefinition(
                        name="filter2",
                        display_name="Filter 2",
                        type="String",
                        is_required=False,
                        is_single_value=False,
                        is_require_any=True,
                        options=[],  # No default
                    ),
                ],
                require_any=True,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is True
        assert params is not None
        assert params.root == {"filter1": "A"}  # Uses the one with default

    async def test_require_any_without_defaults_cannot_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Data source with RequireAny where none have defaults cannot run."""

        async def _fake_get_params(*_a, **_kw):  # noqa: ANN001, ANN002, ANN003, ARG001
            return DataSourceParamsInfo(
                parameters=[
                    ParamDefinition(
                        name="filter1",
                        display_name="Filter 1",
                        type="String",
                        is_required=False,
                        is_single_value=False,
                        is_require_any=True,
                        options=[],
                    ),
                    ParamDefinition(
                        name="filter2",
                        display_name="Filter 2",
                        type="String",
                        is_required=False,
                        is_single_value=False,
                        is_require_any=True,
                        options=[],
                    ),
                ],
                require_any=True,
            )

        monkeypatch.setattr(ds_logic, "get_params_info", _fake_get_params)

        can_run, params = await ds_logic.can_run_without_params("123")
        assert can_run is False
        assert params is None
