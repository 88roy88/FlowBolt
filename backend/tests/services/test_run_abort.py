from __future__ import annotations

import asyncio

import pytest

from flow44.services import run_abort

PROJECT_ID = "test-project-run-abort"


async def test_wake_sets_only_the_watchers_of_that_project() -> None:
    with run_abort.watch(PROJECT_ID) as aborted, run_abort.watch("other-project") as other:
        run_abort._wake(PROJECT_ID)

        assert aborted.is_set()
        assert not other.is_set()

    assert run_abort._watchers == {}


async def test_request_abort_wakes_a_local_run_without_a_listener(test_db: object) -> None:
    assert not run_abort.abort_listener.listening

    with run_abort.watch(PROJECT_ID) as aborted:
        await run_abort.request_abort(PROJECT_ID)

        assert aborted.is_set()


@pytest.mark.usefixtures("setup_test_db")
async def test_abort_reaches_the_run_through_postgres_notify(monkeypatch: pytest.MonkeyPatch) -> None:
    listener = run_abort.AbortListener()
    # request_abort must not take the local shortcut, so the wake can only come back through LISTEN.
    monkeypatch.setattr(run_abort, "abort_listener", listener)
    listener.start()
    try:
        async with asyncio.timeout(5):
            while not listener.listening:  # noqa: ASYNC110 — the flag is the listener's only signal
                await asyncio.sleep(0.01)

        with run_abort.watch(PROJECT_ID) as aborted:
            await run_abort.request_abort(PROJECT_ID)
            await asyncio.wait_for(aborted.wait(), timeout=5)
    finally:
        await listener.stop()
