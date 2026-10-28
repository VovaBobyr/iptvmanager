from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..identity import channel_stable_key, stream_url_key
from ..m3u import parse_m3u
from ..models import Channel, PlaylistSource


@dataclass(frozen=True, slots=True)
class ImportResult:
    found: int
    created: int
    updated: int
    deactivated: int
    unchanged_remote: bool = False


def import_content(session: Session, source: PlaylistSource, content: str) -> ImportResult:
    entries = parse_m3u(content)
    now = datetime.now(UTC)
    existing = {
        channel.stable_key: channel
        for channel in session.scalars(select(Channel).where(Channel.source_id == source.id))
    }
    seen: set[str] = set()
    created = 0
    updated = 0

    for entry in entries:
        stable_key = channel_stable_key(entry.metadata, entry.name, entry.url)
        seen.add(stable_key)
        values = {
            "name": entry.name,
            "stream_url": entry.url,
            "stream_url_key": stream_url_key(entry.url),
            "tvg_id": entry.metadata.get("tvg-id"),
            "tvg_name": entry.metadata.get("tvg-name"),
            "tvg_logo": entry.metadata.get("tvg-logo"),
            "country": entry.metadata.get("tvg-country") or entry.metadata.get("country"),
            "language": entry.metadata.get("tvg-language") or entry.metadata.get("language"),
            "group_title": entry.metadata.get("group-title"),
            "extra_metadata": entry.metadata,
            "active": True,
            "last_seen_at": now,
            "updated_at": now,
        }
        channel = existing.get(stable_key)
        if channel is None:
            session.add(Channel(source_id=source.id, stable_key=stable_key, **values))
            created += 1
        else:
            for key, value in values.items():
                setattr(channel, key, value)
            updated += 1

    stale_keys = set(existing) - seen
    deactivated = 0
    if stale_keys:
        result = session.execute(
            update(Channel)
            .where(
                Channel.source_id == source.id,
                Channel.stable_key.in_(stale_keys),
                Channel.active,
            )
            .values(active=False, updated_at=now)
        )
        deactivated = result.rowcount

    source.refreshed_at = now
    session.commit()
    return ImportResult(len(entries), created, updated, deactivated)


async def refresh_remote_source(
    session: Session, source: PlaylistSource, timeout_seconds: float
) -> ImportResult:
    if source.kind != "remote" or not source.url:
        raise ValueError("Source is not a remote playlist")

    headers = {"User-Agent": "IPTV-Manager/0.1"}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds) as client:
        response = await client.get(source.url, headers=headers)
    if response.status_code == 304:
        return ImportResult(0, 0, 0, 0, unchanged_remote=True)
    response.raise_for_status()
    source.etag = response.headers.get("etag")
    source.last_modified = response.headers.get("last-modified")
    return import_content(session, source, response.text)
