from iptv_manager.api import channel_filters, list_channels
from iptv_manager.models import Channel, PlaylistSource


def _channel(source_id: int, number: int, **values) -> Channel:
    defaults = {
        "name": f"Channel {number}",
        "stream_url": f"https://example.test/{number}",
        "country": "UA",
        "language": "Ukrainian",
        "group_title": "General",
        "health_status": "working",
    }
    defaults.update(values)
    return Channel(
        source_id=source_id,
        stable_key=f"stable-{number}",
        stream_url_key=f"url-{number}",
        **defaults,
    )


def test_channel_filters_split_metadata_and_filter_exact_tokens(session) -> None:
    source = PlaylistSource(name="filters", kind="local")
    session.add(source)
    session.flush()
    session.add_all(
        [
            _channel(
                source.id,
                1,
                country="UA;PL",
                language="Ukrainian;Polish",
                group_title="General;News",
            ),
            _channel(source.id, 2, country="US", language="English", group_title="News"),
            _channel(source.id, 3, group_title="News Local"),
            _channel(source.id, 4, group_title="Sports", health_status="failed"),
        ]
    )
    session.commit()

    facets = channel_filters(
        source_id=source.id,
        health="working",
        active=True,
        session=session,
    )
    categories = {item["value"]: item["count"] for item in facets["categories"]}
    countries = {item["value"]: item["count"] for item in facets["countries"]}

    result = list_channels(
        q=None,
        country=None,
        language=None,
        category="News",
        source_id=source.id,
        health="working",
        active=True,
        page=1,
        page_size=50,
        session=session,
    )

    assert categories == {"General": 1, "News": 2, "News Local": 1}
    assert countries == {"PL": 1, "UA": 2, "US": 1}
    assert result["total"] == 2
    assert {channel.name for channel in result["items"]} == {"Channel 1", "Channel 2"}
