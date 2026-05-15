import asyncio

import pytest

from src.scheduler import Scheduler, safe_run


@pytest.mark.asyncio
async def test_scheduler_runs_registered_jobs():
    called = []

    async def job():
        called.append(1)

    scheduler = Scheduler()
    scheduler.register("test_job", job, interval_seconds=0.1)
    scheduler.start()
    await asyncio.sleep(0.35)
    scheduler.stop()
    assert len(called) >= 2


@pytest.mark.asyncio
async def test_scheduler_handles_job_errors():
    good_calls = []

    async def bad_job():
        raise RuntimeError("oops")

    async def good_job():
        good_calls.append(1)

    scheduler = Scheduler()
    scheduler.register("bad", bad_job, interval_seconds=0.1)
    scheduler.register("good", good_job, interval_seconds=0.1)
    scheduler.start()
    await asyncio.sleep(0.35)
    scheduler.stop()
    assert len(good_calls) >= 2


@pytest.mark.asyncio
async def test_scheduler_stop_is_idempotent():
    scheduler = Scheduler()
    scheduler.stop()  # Should not raise


@pytest.mark.asyncio
async def test_safe_run_swallows_exceptions():
    async def boom():
        raise RuntimeError("explode")

    # Must not raise.
    await safe_run("boom", boom)


@pytest.mark.asyncio
async def test_safe_run_times_out():
    async def sleepy():
        await asyncio.sleep(5)

    # Should return within ~0.1s instead of hanging for 5s.
    start = asyncio.get_event_loop().time()
    await safe_run("sleepy", sleepy, timeout=0.1)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_safe_run_returns_normally_for_successful_jobs():
    calls = []

    async def ok():
        calls.append(1)

    await safe_run("ok", ok)
    assert calls == [1]


@pytest.mark.asyncio
async def test_safe_run_propagates_cancellation():
    async def long():
        await asyncio.sleep(5)

    task = asyncio.create_task(safe_run("long", long, timeout=10.0))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
