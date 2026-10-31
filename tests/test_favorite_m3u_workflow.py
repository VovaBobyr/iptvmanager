from sqlalchemy import select

from iptv_manager.api import verified_live_playlist
from iptv_manager.identity import channel_stable_key, stream_url_key
from iptv_manager.m3u import parse_m3u
from iptv_manager.models import Channel, FavoriteGroup, FavoriteItem, PlaylistSource
from iptv_manager.services.favorites import import_favorites_m3u


def _channel(
    source_id: int,
    name: str,
    url: str,
    tvg_id: str | None,
    *,
    health_status: str = "working",
    active: bool = True,
) -> Channel:
    metadata = {"tvg-id": tvg_id or "", "group-title": "News"}
    return Channel(
        source_id=source_id,
        stable_key=channel_stable_key(metadata, name, url),
        stream_url_key=stream_url_key(url),
        name=name,
        stream_url=url,
        tvg_id=tvg_id,
        country="UA",
        group_title="News",
        health_status=health_status,
        active=active,
    )


def test_live_playlist_exports_only_active_working_channels(session) -> None:
    source = PlaylistSource(name="Source", kind="local")
    session.add(source)
    session.flush()
    session.add_all(
        [
            _channel(source.id, "Live", "https://example.test/live", "live.one"),
            _channel(
                source.id,
                "Failed",
                "https://example.test/failed",
                "failed.one",
                health_status="failed",
            ),
            _channel(
                source.id,
                "Inactive",
                "https://example.test/inactive",
                "inactive.one",
                active=False,
            ),
        ]
    )
    session.commit()

    response = verified_live_playlist(session=session)
    entries = parse_m3u(response.body.decode())

    assert response.headers["content-disposition"] == 'inline; filename="iptv-manager-live.m3u"'
    assert [(entry.name, entry.metadata["tvg-id"]) for entry in entries] == [
        ("Live", "live.one")
    ]
    assert entries[0].metadata["tvg-country"] == "UA"
    assert entries[0].metadata["group-title"] == "UA - News"


def test_favorite_m3u_import_matches_id_then_url_and_skips_duplicates(session) -> None:
    source = PlaylistSource(name="Source", kind="local")
    session.add(source)
    session.flush()
    first = _channel(source.id, "First", "https://example.test/first", "first.id")
    second = _channel(source.id, "Second", "https://example.test/second", None)
    group = FavoriteGroup(name="Selected", slug="selected")
    session.add_all([first, second, group])
    session.commit()

    content = """#EXTM3U
#EXTINF:-1 tvg-id="first.id",First renamed
https://changed.example.test/first
#EXTINF:-1,Second
https://example.test/second
#EXTINF:-1 tvg-id="missing.id",Missing
https://example.test/missing
#EXTINF:-1 tvg-id="first.id",First renamed
https://changed.example.test/first
"""
    result = import_favorites_m3u(session, group, content)
    items = list(
        session.scalars(
            select(FavoriteItem)
            .where(FavoriteItem.group_id == group.id)
            .order_by(FavoriteItem.position)
        )
    )

    assert result.total == 4
    assert result.added == 2
    assert result.already_present == 1
    assert result.unmatched == 1
    assert result.ambiguous == 0
    assert [item.channel_id for item in items] == [first.id, second.id]
    assert items[0].custom_name == "First renamed"
