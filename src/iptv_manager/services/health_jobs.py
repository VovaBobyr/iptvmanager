from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from itertools import batched

import httpx
from sqlalchemy import exists, select, update

from ..config import settings
from ..database import SessionLocal
from ..models import Channel, FavoriteItem, HealthCheck, HealthScanJob
from .health import ProbeResult, probe_url

_tasks: dict[int, asyncio.Task[None]] = {}


def _channel_query(job: HealthScanJob):
    is_favorite = exists().where(FavoriteItem.channel_id == Channel.id)
    query = select(Channel.id, Channel.stream_url).where(Channel.active)
    if job.source_id is not None:
        query = query.where(Channel.source_id == job.source_id)
    if job.favorites_only:
        query = query.where(is_favorite)
    return query.order_by(is_favorite.desc(), Channel.id)


def _record_result(session, channel_id: int, result: ProbeResult) -> None:
    channel = session.get(Channel, channel_id)
    if channel is None:
        return
    channel.health_status = result.status
    session.add(
        HealthCheck(
            channel_id=channel_id,
            status=result.status,
            method=result.method,
            runner_name=settings.runner_name,
            http_status=result.http_status,
            latency_ms=result.latency_ms,
            error_code=result.error_code,
            detail=result.detail,
            checked_at=datetime.now(UTC),
        )
    )


async def run_health_job(job_id: int, *, resume: bool = False) -> None:
    try:
        with SessionLocal() as session:
            job = session.get(HealthScanJob, job_id)
            if job is None:
                return
            channels = list(session.execute(_channel_query(job)).tuples())
            if resume and job.total != len(channels):
                job.status = "stale"
                job.error = (
                    "The channel selection changed since this scan was interrupted. "
                    "Start a new scan instead."
                )
                job.finished_at = datetime.now(UTC)
                session.commit()
                return
            if resume:
                channels = channels[job.completed :]
            else:
                job.total = len(channels)
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.finished_at = None
            job.error = None
            session.commit()

        limits = httpx.Limits(
            max_connections=settings.health_concurrency,
            max_keepalive_connections=settings.health_concurrency,
        )
        timeout = httpx.Timeout(settings.request_timeout_seconds)
        async with httpx.AsyncClient(
            follow_redirects=True, timeout=timeout, limits=limits
        ) as client:
            for channel_batch in batched(channels, settings.health_concurrency):
                results = await asyncio.gather(
                    *(probe_url(url, settings, client) for _, url in channel_batch),
                    return_exceptions=True,
                )
                with SessionLocal() as session:
                    job = session.get(HealthScanJob, job_id)
                    if job is None:
                        return
                    for (channel_id, _url), result in zip(channel_batch, results, strict=True):
                        if isinstance(result, BaseException):
                            result = ProbeResult(
                                "uncertain",
                                "internal",
                                error_code="unexpected_error",
                                detail=str(result),
                            )
                        _record_result(session, channel_id, result)
                        job.completed += 1
                        if result.status == "geographically_restricted":
                            job.geographically_restricted += 1
                        elif result.status == "working":
                            job.working += 1
                        elif result.status == "failed":
                            job.failed += 1
                        else:
                            job.uncertain += 1
                    session.commit()

        with SessionLocal() as session:
            job = session.get(HealthScanJob, job_id)
            if job is not None:
                job.status = "completed"
                job.finished_at = datetime.now(UTC)
                session.commit()
    except asyncio.CancelledError:
        with SessionLocal() as session:
            job = session.get(HealthScanJob, job_id)
            if job is not None:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                session.commit()
        raise
    except Exception as exc:
        with SessionLocal() as session:
            job = session.get(HealthScanJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:2000]
                job.finished_at = datetime.now(UTC)
                session.commit()


def start_health_job(job_id: int, *, resume: bool = False) -> None:
    task = asyncio.create_task(
        run_health_job(job_id, resume=resume), name=f"health-scan-{job_id}"
    )
    _tasks[job_id] = task
    task.add_done_callback(lambda _task: _tasks.pop(job_id, None))


def cancel_health_job(job_id: int) -> bool:
    task = _tasks.get(job_id)
    if task is None or task.done():
        return False
    task.cancel()
    return True


def mark_interrupted_jobs() -> None:
    with SessionLocal() as session:
        session.execute(
            update(HealthScanJob)
            .where(HealthScanJob.status.in_(("queued", "running")))
            .values(
                status="interrupted",
                error="Application stopped before this scan completed",
                finished_at=datetime.now(UTC),
            )
        )
        session.commit()
