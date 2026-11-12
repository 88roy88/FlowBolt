from enum import StrEnum
from unittest.mock import AsyncMock, patch

import pytest

from flow44 import feature_flags
from flow44.config import settings
from flow44.db.feature_flag import FeatureFlagTarget, FlagState, FlagTargetType
from flow44.feature_flags import FlagSpec, get_enabled_flags, is_feature_enabled
from flow44.integrations.directory.client import directory_client


class _Flag(StrEnum):
    beta = "beta"
    other = "other"
    on_by_default = "on_by_default"


GROUP_DN = "CN=Beta Testers,OU=Groups,DC=corp"


def _target(key: str, target_type: FlagTargetType, target_id: str) -> FeatureFlagTarget:
    return FeatureFlagTarget(flag_key=key, target_type=target_type.value, target_id=target_id)


@pytest.fixture(autouse=True)
def _registry():
    # Patched in place: admin.py and others import FLAGS by name.
    with patch.dict(feature_flags.FLAGS, {_Flag.beta: FlagSpec("Beta"), _Flag.other: FlagSpec("Other")}, clear=True):
        yield


def _with_states(*states: FlagState):
    return patch("flow44.feature_flags.list_flag_states", AsyncMock(return_value={s.key: s for s in states}))


async def test_unconfigured_flag_is_off_by_default():
    with _with_states():
        assert await get_enabled_flags("alice") == set()


async def test_unconfigured_flag_uses_code_defaults(monkeypatch):
    monkeypatch.setitem(feature_flags.FLAGS, _Flag.on_by_default, FlagSpec("On", default_for_all=True))
    with _with_states():
        assert await get_enabled_flags("alice") == {"on_by_default"}


async def test_stored_state_overrides_code_default(monkeypatch):
    monkeypatch.setitem(feature_flags.FLAGS, _Flag.on_by_default, FlagSpec("On", default_for_all=True))
    with _with_states(FlagState(key="on_by_default", enabled_for_all=False)):
        assert await get_enabled_flags("alice") == set()


async def test_admin_default(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_ADMIN_IDS", ["admin-user"])
    monkeypatch.setitem(feature_flags.FLAGS, _Flag.beta, FlagSpec("Beta", default_for_admins=True))
    with _with_states():
        assert await get_enabled_flags("admin-user") == {"beta"}
        assert await get_enabled_flags("alice") == set()


async def test_enabled_for_all():
    with _with_states(FlagState(key="beta", enabled_for_all=True)):
        assert await get_enabled_flags("alice") == {"beta"}


async def test_enabled_for_admins_only(monkeypatch):
    monkeypatch.setattr(settings, "SYSTEM_ADMIN_IDS", ["admin-user"])
    with _with_states(FlagState(key="beta", enabled_for_admins=True)):
        assert await get_enabled_flags("admin-user") == {"beta"}
        assert await get_enabled_flags("alice") == set()


async def test_user_target_matches_case_insensitively():
    state = FlagState(key="beta", targets=[_target("beta", FlagTargetType.user, "alice@corp")])
    with _with_states(state):
        assert await get_enabled_flags("Alice@CORP") == {"beta"}
        assert await get_enabled_flags("bob@corp") == set()


async def test_group_target_matches_user_groups(monkeypatch):
    monkeypatch.setattr(directory_client, "get_user_group_ids", AsyncMock(return_value={GROUP_DN}))
    state = FlagState(key="beta", targets=[_target("beta", FlagTargetType.group, GROUP_DN)])
    with _with_states(state):
        assert await get_enabled_flags("alice") == {"beta"}


async def test_group_target_not_matching(monkeypatch):
    monkeypatch.setattr(directory_client, "get_user_group_ids", AsyncMock(return_value={"CN=Someone Else"}))
    state = FlagState(key="beta", targets=[_target("beta", FlagTargetType.group, GROUP_DN)])
    with _with_states(state):
        assert await get_enabled_flags("alice") == set()


@pytest.mark.parametrize(
    ("targets", "expected"),
    [
        pytest.param([_target("beta", FlagTargetType.user, "bob")], set(), id="no-group-targets"),
        pytest.param(
            [_target("beta", FlagTargetType.user, "alice"), _target("beta", FlagTargetType.group, GROUP_DN)],
            {"beta"},
            id="already-on-by-user",
        ),
    ],
)
async def test_no_directory_lookup_when_groups_cant_matter(monkeypatch, targets, expected):
    lookup = AsyncMock(return_value=set())
    monkeypatch.setattr(directory_client, "get_user_group_ids", lookup)
    with _with_states(FlagState(key="beta", targets=targets)):
        assert await get_enabled_flags("alice") == expected
    lookup.assert_not_called()


async def test_flag_removed_from_code_is_ignored():
    with _with_states(FlagState(key="retired", enabled_for_all=True)):
        assert await get_enabled_flags("alice") == set()


async def test_is_feature_enabled_reads_only_that_flag():
    lookup = AsyncMock(return_value={"beta": FlagState(key="beta", enabled_for_all=True)})
    with patch("flow44.feature_flags.list_flag_states", lookup):
        assert await is_feature_enabled("alice", _Flag.beta) is True
        assert await is_feature_enabled("alice", _Flag.other) is False
    assert [list(call.args[0]) for call in lookup.call_args_list] == [["beta"], ["other"]]
