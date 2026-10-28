from iptv_manager.m3u import M3UEntry, parse_m3u, render_m3u


def test_export_is_valid_extended_m3u() -> None:
    rendered = render_m3u(
        [
            M3UEntry(
                "News One",
                "https://example.test/live.m3u8",
                {"tvg-id": "news.one", "group-title": "My News"},
            )
        ]
    )
    assert rendered.startswith("#EXTM3U\n#EXTINF:-1")
    assert parse_m3u(rendered)[0].metadata["group-title"] == "My News"
