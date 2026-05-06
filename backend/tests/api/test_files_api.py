"""Integration tests for file CRUD/upload API endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi.testclient import TestClient

from flow44.api.sandbox import get_sandbox
from flow44.main import app
from flow44.sandbox.base import BaseSandbox, SandboxInfo
from flow44.sandbox.filesystem_mixin import FileSystemMixin

PROJECT_ID = "test-project-files-api"


class APITestSandbox(FileSystemMixin, BaseSandbox):
    def exec(self, command: str) -> AsyncIterator[str]:  # type: ignore[override]
        raise NotImplementedError

    async def _spawn_background(self, name: str, command: str, env: dict[str, str]) -> None:
        raise NotImplementedError

    def create_pty(self):  # type: ignore[override]
        raise NotImplementedError

    @classmethod
    def find_pids_in_port_range(cls, port_start: int, port_end: int) -> list[tuple[int, int]]:
        raise NotImplementedError

    @classmethod
    def kill_pid(cls, pid: int) -> None:
        raise NotImplementedError


def _override_sandbox(workspace_dir: Path) -> APITestSandbox:
    info = SandboxInfo(project_id=PROJECT_ID, workspace_dir=str(workspace_dir), port=0)
    return APITestSandbox(info)


client = TestClient(app)


def test_create_entry_and_conflict(tmp_path: Path) -> None:
    sandbox = _override_sandbox(tmp_path)
    app.dependency_overrides[get_sandbox] = lambda project_id: sandbox
    try:
        response = client.post(
            f"/api/files/{PROJECT_ID}/file",
            json={"path": "/src/new.ts", "content": "export const x = 1;\n"},
        )
        assert response.status_code == 200
        assert (tmp_path / "src" / "new.ts").read_text(encoding="utf-8") == "export const x = 1;\n"

        conflict_response = client.post(
            f"/api/files/{PROJECT_ID}/file",
            json={"path": "/src/new.ts", "content": "duplicate"},
        )
        assert conflict_response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_sandbox, None)


def test_rename_entry_success_and_failures(tmp_path: Path) -> None:
    sandbox = _override_sandbox(tmp_path)
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "old.ts").write_text("old-content", encoding="utf-8")
    (tmp_path / "src" / "existing.ts").write_text("existing", encoding="utf-8")

    app.dependency_overrides[get_sandbox] = lambda project_id: sandbox
    try:
        response = client.patch(
            f"/api/files/{PROJECT_ID}/file",
            json={"old_path": "/src/old.ts", "new_path": "/src/new.ts"},
        )
        assert response.status_code == 200
        assert not (tmp_path / "src" / "old.ts").exists()
        assert (tmp_path / "src" / "new.ts").read_text(encoding="utf-8") == "old-content"

        missing_response = client.patch(
            f"/api/files/{PROJECT_ID}/file",
            json={"old_path": "/src/missing.ts", "new_path": "/src/unused.ts"},
        )
        assert missing_response.status_code == 404

        conflict_response = client.patch(
            f"/api/files/{PROJECT_ID}/file",
            json={"old_path": "/src/new.ts", "new_path": "/src/existing.ts"},
        )
        assert conflict_response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_sandbox, None)


def test_delete_entry_non_empty_directory(tmp_path: Path) -> None:
    sandbox = _override_sandbox(tmp_path)
    (tmp_path / "src" / "assets").mkdir(parents=True)
    (tmp_path / "src" / "assets" / "logo.svg").write_text("<svg />", encoding="utf-8")

    app.dependency_overrides[get_sandbox] = lambda project_id: sandbox
    try:
        response = client.delete(
            f"/api/files/{PROJECT_ID}/file",
            params={"path": "/src"},
        )
        assert response.status_code == 200
        assert not (tmp_path / "src").exists()
    finally:
        app.dependency_overrides.pop(get_sandbox, None)


def test_upload_entry_writes_binary_and_conflict(tmp_path: Path) -> None:
    sandbox = _override_sandbox(tmp_path)
    app.dependency_overrides[get_sandbox] = lambda project_id: sandbox
    payload = b"\x89PNG\r\n\x1a\n"
    try:
        response = client.post(
            f"/api/files/{PROJECT_ID}/file/upload",
            params={"path": "/src/assets/logo.png"},
            content=payload,
            headers={"Content-Type": "application/octet-stream"},
        )
        assert response.status_code == 200
        assert (tmp_path / "src" / "assets" / "logo.png").read_bytes() == payload

        conflict_response = client.post(
            f"/api/files/{PROJECT_ID}/file/upload",
            params={"path": "/src/assets/logo.png"},
            content=b"new-content",
            headers={"Content-Type": "application/octet-stream"},
        )
        assert conflict_response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_sandbox, None)
