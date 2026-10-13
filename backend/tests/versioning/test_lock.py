import asyncio
from datetime import datetime

import pytest

from flow44.db.heartbeat import clear_heartbeat
from flow44.services.versioning import service as versioning

from .conftest import VersionChain, requires_git

pytestmark = [pytest.mark.asyncio, requires_git]


async def test_begin_turn_and_preview_never_claim_a_detached_workspace(
    project_id: str, version_chain: VersionChain
) -> None:
    for _ in range(20):
        claim_result, preview_result = await asyncio.gather(
            versioning.begin_turn(project_id),
            versioning.preview_version(project_id, version_chain.shas[0]),
            return_exceptions=True,
        )
        claimed_at = claim_result if isinstance(claim_result, datetime) else None

        assert not (claimed_at and version_chain.git.is_detached())
        assert isinstance(claim_result, (datetime, versioning.WorkspaceLocked))
        assert preview_result is None or isinstance(preview_result, versioning.WorkspaceLocked)

        if claimed_at:
            await clear_heartbeat(project_id, only_beat=claimed_at)
        await versioning.exit_preview(project_id)
