from iptv_manager.m3u import M3UEntry, parse_m3u, render_m3u


def test_parse_extended_m3u() -> None:
    content = '''#EXTM3U
#EXTINF:-1 tvg-id="news.example" tvg-logo="https://img/logo.png" group-title="News",Example News
https://stream.example/live.m3u8
'''

    entries = parse_m3u(content)

    assert len(entries) == 1
    assert entries[0].name == "Example News"
    assert entries[0].metadata["tvg-id"] == "news.example"
    assert entries[0].metadata["group-title"] == "News"


def test_render_round_trip() -> None:
    original = M3UEntry(
        name="Example TV",
        url="https://stream.example/tv",
        metadata={"tvg-id": "example.tv", "group-title": "Favorites"},
    )

    rendered = render_m3u([original])
    parsed = parse_m3u(rendered)

    assert parsed == [original]


def test_parser_accepts_plain_urls() -> None:
    entries = parse_m3u("#EXTM3U\nhttps://example.test/channel.ts\n")
    assert entries[0].url == "https://example.test/channel.ts"
