from dataclasses import dataclass
from enum import StrEnum

from flow44.auth.permissions import is_admin
from flow44.db.feature_flag import FlagState, FlagTargetType, list_flag_states
from flow44.integrations.directory.client import directory_client


class FeatureFlag(StrEnum):
    disable_workspaces = "disable_workspaces"
    disable_workspaces_exempt = "disable_workspaces_exempt"
    model_selector = "model_selector"


@dataclass(frozen=True)
class FlagSpec:
    description: str
    default_for_all: bool = False
    default_for_admins: bool = False
    danger: bool = False  # the admin UI shows it in red and asks before turning it on


FLAGS: dict[FeatureFlag, FlagSpec] = {
    FeatureFlag.disable_workspaces: FlagSpec(
        "Kill switch for when the backend is overloaded. Users it's turned on for can't open, edit or create "
        "projects, unless disable_workspaces_exempt is on for them. Published apps and the admin panel keep working.",
        danger=True,
    ),
    FeatureFlag.disable_workspaces_exempt: FlagSpec(
        "Whitelist for disable_workspaces: users it's turned on for keep working while the kill switch is on.",
    ),
    FeatureFlag.model_selector: FlagSpec(
        "Show the model dropdown in the chat input. When off, chats use the project's model.",
    ),
}


def default_flag_state(key: str, spec: FlagSpec) -> FlagState:
    return FlagState(key=key, enabled_for_all=spec.default_for_all, enabled_for_admins=spec.default_for_admins)


def resolve_flag_state(key: str, spec: FlagSpec, states: dict[str, FlagState]) -> FlagState:
    return states.get(key) or default_flag_state(key, spec)


async def get_enabled_flags(user_id: str) -> set[str]:
    return await _get_enabled_among(user_id, FLAGS)


async def is_feature_enabled(user_id: str, flag: FeatureFlag) -> bool:
    return bool(await _get_enabled_among(user_id, {flag: FLAGS[flag]}))


async def _get_enabled_among(user_id: str, flags: dict[FeatureFlag, FlagSpec]) -> set[str]:
    states = await list_flag_states(flags.keys())
    admin = is_admin(user_id)

    enabled: set[str] = set()
    group_targets: dict[str, set[str]] = {}
    for key, spec in flags.items():
        state = resolve_flag_state(key, spec, states)
        if (
            state.enabled_for_all
            or (state.enabled_for_admins and admin)
            or any(t.target_type == FlagTargetType.user and t.target_id == user_id for t in state.targets)
        ):
            enabled.add(key)
        elif groups := {t.target_id for t in state.targets if t.target_type == FlagTargetType.group}:
            group_targets[key] = groups

    # Only ask the directory when a group could still turn a flag on.
    if group_targets:
        user_groups = await directory_client.get_user_group_ids(user_id)
        enabled |= {key for key, groups in group_targets.items() if groups & user_groups}
    return enabled
