from sqlalchemy import select

from iptv_manager.models import Channel, FavoriteGroup, FavoriteItem, PlaylistSource
from iptv_manager.services.importer import _backfill_source_metadata, import_content

FIRST = '''#EXTM3U
#EXTINF:-1 tvg-id="one" group-title="News",One
https://example.test/one-v1
#EXTINF:-1 tvg-id="two" group-title="Music",Two
https://example.test/two
'''

SECOND = '''#EXTM3U
#EXTINF:-1 tvg-id="one" group-title="News",One renamed
https://example.test/one-v2
'''

COUNTRY_FROM_ID = '''#EXTM3U
#EXTINF:-1 tvg-id="ExampleChannel.ua@HD" group-title="News",Example
https://example.test/ua
'''


def test_refresh_updates_in_place_and_preserves_favorite(session) -> None:
    source = PlaylistSource(name="Test", kind="local")
    session.add(source)
    session.flush()
    initial = import_content(session, source, FIRST)
    channels = list(session.scalars(select(Channel).order_by(Channel.name)))
    original_id = channels[0].id
    group = FavoriteGroup(name="Living room", slug="living-room")
    session.add(group)
    session.flush()
    session.add(FavoriteItem(group_id=group.id, channel_id=original_id, position=0))
    session.commit()

    refreshed = import_content(session, source, SECOND)
    one = session.scalar(select(Channel).where(Channel.tvg_id == "one"))
    two = session.scalar(select(Channel).where(Channel.tvg_id == "two"))
    favorite = session.scalar(select(FavoriteItem))

    assert initial.created == 2
    assert refreshed.created == 0
    assert refreshed.deactivated == 1
    assert one.id == original_id
    assert one.name == "One renamed"
    assert one.stream_url.endswith("one-v2")
    assert two.active is False
    assert favorite.channel_id == original_id


def test_missing_favorite_is_preserved_and_reactivated_when_channel_returns(session) -> None:
    source = PlaylistSource(name="Returning", kind="local")
    session.add(source)
    session.flush()
    import_content(session, source, FIRST)
    channel = session.scalar(select(Channel).where(Channel.tvg_id == "two"))
    original_id = channel.id
    group = FavoriteGroup(name="Music", slug="music")
    session.add(group)
    session.flush()
    session.add(FavoriteItem(group_id=group.id, channel_id=original_id, position=0))
    session.commit()

    import_content(session, source, SECOND)
    session.expire_all()
    missing = session.get(Channel, original_id)
    favorite = session.scalar(select(FavoriteItem))

    assert missing.active is False
    assert favorite.channel_id == original_id

    import_content(session, source, FIRST)
    session.expire_all()
    returned = session.get(Channel, original_id)
    favorite = session.scalar(select(FavoriteItem))

    assert returned.active is True
    assert favorite.channel_id == original_id


def test_import_derives_country_from_iptv_org_channel_id(session) -> None:
    source = PlaylistSource(name="Country", kind="local")
    session.add(source)
    session.flush()

    import_content(session, source, COUNTRY_FROM_ID)
    channel = session.scalar(select(Channel))

    assert channel.country == "UA"


def test_existing_channels_receive_country_metadata_backfill(session) -> None:
    source = PlaylistSource(name="Backfill", kind="remote", url="https://example.test/list.m3u")
    session.add(source)
    session.flush()
    channel = Channel(
        source_id=source.id,
        stable_key="existing",
        stream_url_key="existing-url",
        name="Existing",
        stream_url="https://example.test/existing",
        tvg_id="ExistingChannel.pl@SD",
    )
    session.add(channel)
    session.commit()

    updated = _backfill_source_metadata(session, source.id)
    session.refresh(channel)

    assert updated == 1
    assert channel.country == "PL"
