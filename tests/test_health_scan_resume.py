from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from iptv_manager import api
from iptv_manager.models import Channel, HealthCheck, HealthScanJob, PlaylistSource
from iptv_manager.services import health_jobs
from iptv_manager.services.health import ProbeResult


@pytest.mark.asyncio
async def test_resume_interrupted_scan_preserves_progress(session, monkeypatch):
    job = HealthScanJob(
        status="interrupted",
        total=100,
        completed=35,
        working=20,
        failed=10,
        uncertain=5,
        error="Application stopped before this scan completed",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    started = []
    monkeypatch.setattr(
        api,
        "start_health_job",
        lambda job_id, *, resume=False: started.append((job_id, resume)),
    )

    result = await api.resume_health_scan(job.id, session)

    assert result["status"] == "queued"
    assert result["completed"] == 35
    assert result["working"] == 20
    assert result["error"] is None
    assert started == [(job.id, True)]


@pytest.mark.asyncio
async def test_completed_scan_cannot_be_resumed(session):
    job = HealthScanJob(status="completed", total=10, completed=10)
    session.add(job)
    session.commit()
    session.refresh(job)

    with pytest.raises(HTTPException) as exc_info:
        await api.resume_health_scan(job.id, session)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_resumed_worker_skips_completed_channels(session, monkeypatch):
    source = PlaylistSource(name="resume-source", kind="local")
    session.add(source)
    session.flush()
    channels = [
        Channel(
            source_id=source.id,
            stable_key=f"stable-{number}",
            stream_url_key=f"url-{number}",
            name=f"Channel {number}",
            stream_url=f"https://example.test/{number}.m3u8",
        )
        for number in range(3)
    ]
    session.add_all(channels)
    session.flush()
    job = HealthScanJob(
        source_id=source.id,
        status="interrupted",
        total=3,
        completed=1,
        working=1,
    )
    session.add(job)
    session.commit()
    factory = sessionmaker(bind=session.get_bind(), expire_on_commit=False)

    async def successful_probe(*_args, **_kwargs):
        return ProbeResult(status="working", method="test")

    monkeypatch.setattr(health_jobs, "SessionLocal", factory)
    monkeypatch.setattr(health_jobs, "probe_url", successful_probe)

    await health_jobs.run_health_job(job.id, resume=True)

    session.expire_all()
    resumed_job = session.get(HealthScanJob, job.id)
    checked_channel_ids = set(session.scalars(select(HealthCheck.channel_id)))
    assert resumed_job.status == "completed"
    assert resumed_job.completed == 3
    assert resumed_job.working == 3
    assert checked_channel_ids == {channels[1].id, channels[2].id}
