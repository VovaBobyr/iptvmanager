from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .database import SessionLocal, create_schema, get_session
from .m3u import M3UEntry, render_m3u
from .models import (
    Channel,
    FavoriteGroup,
    FavoriteItem,
    HealthCheck,
    HealthScanJob,
    PlaylistSource,
)
from .schemas import (
    ChannelRead,
    FavoriteAdd,
    GroupCreate,
    HealthScanCreate,
    InlineImport,
    ReorderFavorites,
    SourceCreate,
    SourceRead,
)
from .services.backups import create_database_backup, restore_database_backup
from .services.health import probe_url, save_result
from .services.health_jobs import cancel_health_job, mark_interrupted_jobs, start_health_job
from .services.importer import import_content, refresh_remote_source

router = APIRouter(prefix="/api")
playlist_router = APIRouter(prefix="/playlists")
MAX_BACKUP_BYTES = 512 * 1024 * 1024


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "favorites"


def _scan_job_dict(job: HealthScanJob) -> dict[str, object]:
    return {
        "id": job.id,
        "source_id": job.source_id,
        "favorites_only": job.favorites_only,
        "status": job.status,
        "total": job.total,
        "completed": job.completed,
        "working": job.working,
        "failed": job.failed,
        "uncertain": job.uncertain,
        "geographically_restricted": job.geographically_restricted,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.get("/backups/database")
def download_database_backup() -> Response:
    try:
        content = create_database_backup(settings.database_url)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Response(
        content,
        media_type="application/vnd.sqlite3",
        headers={
            "Content-Disposition": f'attachment; filename="iptv-manager-{timestamp}.db"'
        },
    )


@router.put("/backups/database")
async def restore_database(request: Request) -> dict[str, str]:
    content_length = int(request.headers.get("content-length", "0") or 0)
    if content_length > MAX_BACKUP_BYTES:
        raise HTTPException(413, "Database backup exceeds the 512 MB upload limit")
    with SessionLocal() as session:
        active_job = session.scalar(
            select(HealthScanJob).where(HealthScanJob.status.in_(("queued", "running")))
        )
        if active_job is not None:
            raise HTTPException(409, "Stop the active health scan before restoring a backup")
    content = await request.body()
    if not content:
        raise HTTPException(422, "The backup file is empty")
    if len(content) > MAX_BACKUP_BYTES:
        raise HTTPException(413, "Database backup exceeds the 512 MB upload limit")
    try:
        safety_backup = restore_database_backup(settings.database_url, content)
        create_schema()
        mark_interrupted_jobs()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "status": "restored",
        "safety_backup": safety_backup.name,
        "message": "Database restored. Reload the dashboard to use the restored data.",
    }


@router.get("/sources", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_session)) -> list[PlaylistSource]:
    return list(session.scalars(select(PlaylistSource).order_by(PlaylistSource.name)))


@router.post("/sources", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, session: Session = Depends(get_session)) -> PlaylistSource:
    if payload.kind not in {"remote", "local"}:
        raise HTTPException(422, "kind must be 'remote' or 'local'")
    if payload.kind == "remote" and not payload.url:
        raise HTTPException(422, "remote sources require a URL")
    source = PlaylistSource(name=payload.name, kind=payload.kind, url=payload.url)
    session.add(source)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "A source with this name already exists") from exc
    session.refresh(source)
    return source


@router.post("/sources/{source_id}/refresh")
async def refresh_source(
    source_id: int, session: Session = Depends(get_session)
) -> dict[str, int | bool]:
    source = session.get(PlaylistSource, source_id)
    if source is None:
        raise HTTPException(404, "Source not found")
    try:
        result = await refresh_remote_source(session, source, settings.request_timeout_seconds)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Playlist refresh failed: {exc}") from exc
    return asdict(result)


@router.post("/imports/inline")
def import_inline(
    payload: InlineImport, session: Session = Depends(get_session)
) -> dict[str, int | bool]:
    source = session.scalar(
        select(PlaylistSource).where(PlaylistSource.name == payload.source_name)
    )
    if source is None:
        source = PlaylistSource(name=payload.source_name, kind="local")
        session.add(source)
        session.flush()
    result = import_content(session, source, payload.content)
    return asdict(result)


@router.get("/channels")
def list_channels(
    q: str | None = None,
    country: str | None = None,
    language: str | None = None,
    category: str | None = None,
    source_id: int | None = None,
    health: str | None = None,
    active: bool | None = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    filters = []
    if q:
        filters.append(Channel.name.ilike(f"%{q}%"))
    for value, column in (
        (country, Channel.country),
        (language, Channel.language),
        (category, Channel.group_title),
        (source_id, Channel.source_id),
        (health, Channel.health_status),
        (active, Channel.active),
    ):
        if value is not None:
            filters.append(column == value)
    total = session.scalar(select(func.count()).select_from(Channel).where(*filters)) or 0
    channels = list(
        session.scalars(
            select(Channel)
            .where(*filters)
            .order_by(Channel.name, Channel.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [ChannelRead.model_validate(channel) for channel in channels],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/channels/{channel_id}")
def channel_detail(channel_id: int, session: Session = Depends(get_session)) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    checks = list(
        session.scalars(
            select(HealthCheck)
            .where(HealthCheck.channel_id == channel_id)
            .order_by(HealthCheck.checked_at.desc())
            .limit(100)
        )
    )
    return {
        "channel": ChannelRead.model_validate(channel),
        "checks": [
            {
                "id": check.id,
                "status": check.status,
                "method": check.method,
                "runner_name": check.runner_name,
                "http_status": check.http_status,
                "latency_ms": check.latency_ms,
                "error_code": check.error_code,
                "detail": check.detail,
                "checked_at": check.checked_at,
            }
            for check in checks
        ],
    }


@router.post("/channels/{channel_id}/check")
async def check_channel(
    channel_id: int, session: Session = Depends(get_session)
) -> dict[str, object]:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(404, "Channel not found")
    result = await probe_url(channel.stream_url, settings)
    check = save_result(session, channel, result, settings.runner_name)
    return {
        "id": check.id,
        "status": check.status,
        "method": check.method,
        "runner_name": check.runner_name,
        "http_status": check.http_status,
        "latency_ms": check.latency_ms,
        "error_code": check.error_code,
        "detail": check.detail,
        "checked_at": check.checked_at,
    }


@router.get("/health-scans")
def list_health_scans(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    jobs = session.scalars(select(HealthScanJob).order_by(HealthScanJob.id.desc()).limit(20))
    return [_scan_job_dict(job) for job in jobs]


@router.post("/health-scans", status_code=status.HTTP_202_ACCEPTED)
async def create_health_scan(
    payload: HealthScanCreate, session: Session = Depends(get_session)
) -> dict[str, object]:
    active_job = session.scalar(
        select(HealthScanJob).where(HealthScanJob.status.in_(("queued", "running")))
    )
    if active_job is not None:
        raise HTTPException(409, f"Health scan {active_job.id} is already active")
    if payload.source_id is not None and session.get(PlaylistSource, payload.source_id) is None:
        raise HTTPException(404, "Source not found")
    job = HealthScanJob(
        source_id=payload.source_id,
        favorites_only=payload.favorites_only,
        status="queued",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    start_health_job(job.id)
    return _scan_job_dict(job)


@router.get("/health-scans/{job_id}")
def get_health_scan(
    job_id: int, session: Session = Depends(get_session)
) -> dict[str, object]:
    job = session.get(HealthScanJob, job_id)
    if job is None:
        raise HTTPException(404, "Health scan not found")
    return _scan_job_dict(job)


@router.post("/health-scans/{job_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_health_scan(
    job_id: int, session: Session = Depends(get_session)
) -> dict[str, object]:
    job = session.get(HealthScanJob, job_id)
    if job is None:
        raise HTTPException(404, "Health scan not found")
    active_job = session.scalar(
        select(HealthScanJob).where(
            HealthScanJob.status.in_(("queued", "running")),
            HealthScanJob.id != job_id,
        )
    )
    if active_job is not None:
        raise HTTPException(409, f"Health scan {active_job.id} is already active")
    if job.status not in {"interrupted", "cancelled", "failed"}:
        raise HTTPException(409, "Only an interrupted, cancelled, or failed scan can be resumed")
    if job.total <= 0 or job.completed >= job.total:
        raise HTTPException(409, "This health scan has no remaining channels")
    job.status = "queued"
    job.error = None
    job.finished_at = None
    session.commit()
    session.refresh(job)
    start_health_job(job.id, resume=True)
    return _scan_job_dict(job)


@router.delete("/health-scans/{job_id}", status_code=status.HTTP_202_ACCEPTED)
async def cancel_health_scan(
    job_id: int, session: Session = Depends(get_session)
) -> dict[str, object]:
    job = session.get(HealthScanJob, job_id)
    if job is None:
        raise HTTPException(404, "Health scan not found")
    if job.status not in {"queued", "running"}:
        raise HTTPException(409, "Health scan is not active")
    if not cancel_health_job(job_id):
        job.status = "cancelled"
        session.commit()
    return {"id": job_id, "status": "cancelling"}


@router.get("/favorite-groups")
def list_groups(session: Session = Depends(get_session)) -> list[dict[str, object]]:
    groups = session.scalars(
        select(FavoriteGroup).options(selectinload(FavoriteGroup.items)).order_by(FavoriteGroup.name)
    )
    return [
        {"id": group.id, "name": group.name, "slug": group.slug, "item_count": len(group.items)}
        for group in groups
    ]


@router.post("/favorite-groups", status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate, session: Session = Depends(get_session)
) -> dict[str, object]:
    base_slug = _slugify(payload.name)
    slug = base_slug
    suffix = 2
    while session.scalar(select(FavoriteGroup.id).where(FavoriteGroup.slug == slug)):
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    group = FavoriteGroup(name=payload.name, slug=slug)
    session.add(group)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "A favorite group with this name already exists") from exc
    session.refresh(group)
    return {"id": group.id, "name": group.name, "slug": group.slug}


@router.delete("/favorite-groups/{group_id}", status_code=204)
def delete_group(group_id: int, session: Session = Depends(get_session)) -> None:
    group = session.get(FavoriteGroup, group_id)
    if group is None:
        raise HTTPException(404, "Favorite group not found")
    session.delete(group)
    session.commit()


@router.post("/favorite-groups/{group_id}/items", status_code=status.HTTP_201_CREATED)
def add_favorite(
    group_id: int, payload: FavoriteAdd, session: Session = Depends(get_session)
) -> dict[str, int]:
    group = session.get(FavoriteGroup, group_id)
    channel = session.get(Channel, payload.channel_id)
    if group is None or channel is None:
        raise HTTPException(404, "Favorite group or channel not found")
    max_position = session.scalar(
        select(func.max(FavoriteItem.position)).where(FavoriteItem.group_id == group_id)
    )
    item = FavoriteItem(
        group_id=group_id, channel_id=payload.channel_id, position=(max_position or -1) + 1
    )
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "Channel is already in this group") from exc
    session.refresh(item)
    return {"id": item.id}


@router.delete("/favorite-groups/{group_id}/items/{channel_id}", status_code=204)
def remove_favorite(
    group_id: int, channel_id: int, session: Session = Depends(get_session)
) -> None:
    item = session.scalar(
        select(FavoriteItem).where(
            FavoriteItem.group_id == group_id, FavoriteItem.channel_id == channel_id
        )
    )
    if item is None:
        raise HTTPException(404, "Favorite not found")
    session.delete(item)
    session.commit()


@router.put("/favorite-groups/{group_id}/order")
def reorder_favorites(
    group_id: int, payload: ReorderFavorites, session: Session = Depends(get_session)
) -> dict[str, int]:
    items = list(session.scalars(select(FavoriteItem).where(FavoriteItem.group_id == group_id)))
    by_channel = {item.channel_id: item for item in items}
    if set(payload.channel_ids) != set(by_channel) or len(payload.channel_ids) != len(by_channel):
        raise HTTPException(422, "channel_ids must contain every group channel exactly once")
    for position, channel_id in enumerate(payload.channel_ids):
        by_channel[channel_id].position = position
    session.commit()
    return {"updated": len(items)}


@playlist_router.get("/{slug}.m3u")
def favorite_playlist(slug: str, session: Session = Depends(get_session)) -> Response:
    group = session.scalar(
        select(FavoriteGroup)
        .where(FavoriteGroup.slug == slug)
        .options(selectinload(FavoriteGroup.items).selectinload(FavoriteItem.channel))
    )
    if group is None:
        raise HTTPException(404, "Favorite group not found")
    entries = [
        M3UEntry(
            name=item.custom_name or item.channel.name,
            url=item.channel.stream_url,
            metadata={
                "tvg-id": item.channel.tvg_id or "",
                "tvg-name": item.channel.tvg_name or item.channel.name,
                "tvg-logo": item.channel.tvg_logo or "",
                "tvg-country": item.channel.country or "",
                "tvg-language": item.channel.language or "",
                "group-title": group.name,
            },
        )
        for item in group.items
    ]
    return Response(
        render_m3u(entries),
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": f'inline; filename="{group.slug}.m3u"'},
    )
