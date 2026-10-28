from sqlalchemy import select

from iptv_manager.models import Channel, FavoriteGroup, FavoriteItem, PlaylistSource
from iptv_manager.services.importer import import_content

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
