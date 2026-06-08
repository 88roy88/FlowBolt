from enum import StrEnum


class Permission(StrEnum):
    read = "read"
    write = "write"
    publish = "publish"
    delete = "delete"
    manage_members = "manage_members"
    read_all = "read_all"
    write_all = "write_all"
    publish_all = "publish_all"


class Role(StrEnum):
    viewer = "viewer"
    editor = "editor"
    publisher = "publisher"
    maintainer = "maintainer"


ROLE_PERMISSIONS: dict[Role, set[Permission]] = {
    Role.viewer: {Permission.read},
    Role.editor: {Permission.read, Permission.write},
    Role.publisher: {Permission.read, Permission.publish},
    Role.maintainer: {Permission.read, Permission.write, Permission.publish},
}

_OWNER_PERMISSIONS: set[Permission] = {
    Permission.read,
    Permission.write,
    Permission.publish,
    Permission.delete,
    Permission.manage_members,
}

_ADMIN_PERMISSIONS: set[Permission] = {
    Permission.read_all,
    Permission.write_all,
    Permission.publish_all,
    Permission.delete,
    Permission.manage_members,
}

_ALL_VARIANTS: dict[Permission, Permission] = {
    Permission.read: Permission.read_all,
    Permission.write: Permission.write_all,
    Permission.publish: Permission.publish_all,
}


def get_role_permissions(role: Role) -> set[Permission]:
    return ROLE_PERMISSIONS[role]


def get_owner_permissions() -> set[Permission]:
    return _OWNER_PERMISSIONS


def get_admin_permissions() -> set[Permission]:
    return _ADMIN_PERMISSIONS


def has_permission(user_permissions: set[Permission], required: Permission) -> bool:
    if required in user_permissions:
        return True
    all_variant = _ALL_VARIANTS.get(required)
    return bool(all_variant and all_variant in user_permissions)
