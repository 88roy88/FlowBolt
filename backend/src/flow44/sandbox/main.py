from abc import ABC

from flow44.sandbox.base import BaseSandbox
from flow44.sandbox.filesystem_mixin import FileSystemMixin
from flow44.sandbox.namespaced import NamespacedSandbox
from flow44.sandbox.pnpm_mixin import PnpmMixin
from flow44.sandbox.search_mixin import SearchMixin
from flow44.sandbox.unix_local import UnixSandbox
from flow44.sandbox.windows_local import WindowsLocalSandbox


class FileSystemSandbox(FileSystemMixin, BaseSandbox, ABC):
    pass


class SearchableSandbox(SearchMixin, BaseSandbox, ABC):
    pass


class PnpmSandbox(PnpmMixin, FileSystemSandbox, SearchableSandbox, ABC):
    pass


class PnpmSandboxUnix(PnpmSandbox, UnixSandbox):
    pass


class PnpmSandboxNamespace(PnpmSandbox, NamespacedSandbox):
    pass


class PnpmSandboxWindows(PnpmSandbox, WindowsLocalSandbox):
    pass
