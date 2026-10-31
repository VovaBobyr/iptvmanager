from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..identity import normalize_text, stream_url_key
from ..m3u import M3UEntry, parse_m3u
from ..models import Channel, FavoriteGroup, FavoriteItem


@dataclass(frozen=True, slots=True)
class FavoriteImportResult:
    total: int
    added: int
    already_present: int
    unmatched: int
    ambiguous: int


def _resolve_candidate(
    candidates: list[Channel], entry_url_key: str
) -> tuple[Channel | None, bool]:
    if len(candidates) == 1:
        return candidates[0], False
    matching_url = [channel for channel in candidates if channel.stream_url_key == entry_url_key]
    if len(matching_url) == 1:
        return matching_url[0], False
    return None, bool(candidates)


def _match_channel(
    entry: M3UEntry,
    by_tvg_id: dict[str, list[Channel]],
    by_url: dict[str, list[Channel]],
) -> tuple[Channel | None, bool]:
    entry_url_key = stream_url_key(entry.url)
    tvg_id = normalize_text(entry.metadata.get("tvg-id"))
    if tvg_id:
        candidates = by_tvg_id.get(tvg_id, [])
        if candidates:
            return _resolve_candidate(candidates, entry_url_key)
    return _resolve_candidate(by_url.get(entry_url_key, []), entry_url_key)


def import_favorites_m3u(
    session: Session, group: FavoriteGroup, content: str
) -> FavoriteImportResult:
    entries = parse_m3u(content)
    if not entries:
        raise ValueError("The M3U file does not contain any channels")

    channels = list(session.scalars(select(Channel).order_by(Channel.active.desc(), Channel.id)))
    by_tvg_id: dict[str, list[Channel]] = defaultdict(list)
    by_url: dict[str, list[Channel]] = defaultdict(list)
    for channel in channels:
        if channel.tvg_id:
            by_tvg_id[normalize_text(channel.tvg_id)].append(channel)
        by_url[channel.stream_url_key].append(channel)

    existing_ids = set(
        session.scalars(
            select(FavoriteItem.channel_id).where(FavoriteItem.group_id == group.id)
        )
    )
    max_position = session.scalar(
        select(func.max(FavoriteItem.position)).where(FavoriteItem.group_id == group.id)
    )
    next_position = (max_position if max_position is not None else -1) + 1
    added = already_present = unmatched = ambiguous = 0

    for entry in entries:
        channel, is_ambiguous = _match_channel(entry, by_tvg_id, by_url)
        if channel is None:
            if is_ambiguous:
                ambiguous += 1
            else:
                unmatched += 1
            continue
        if channel.id in existing_ids:
            already_present += 1
            continue

        custom_name = (
            entry.name if normalize_text(entry.name) != normalize_text(channel.name) else None
        )
        session.add(
            FavoriteItem(
                group_id=group.id,
                channel_id=channel.id,
                position=next_position,
                custom_name=custom_name,
            )
        )
        existing_ids.add(channel.id)
        next_position += 1
        added += 1

    session.commit()
    return FavoriteImportResult(
        total=len(entries),
        added=added,
        already_present=already_present,
        unmatched=unmatched,
        ambiguous=ambiguous,
    )
