from iptv_manager.identity import channel_stable_key, normalize_stream_url, stream_url_key


def test_tvg_id_survives_url_rotation() -> None:
    metadata = {"tvg-id": "Example.TV"}
    first = channel_stable_key(metadata, "Example", "https://a.test/one")
    second = channel_stable_key(metadata, "Renamed", "https://b.test/two")
    assert first == second


def test_volatile_query_tokens_do_not_change_url_fingerprint() -> None:
    first = "HTTPS://EXAMPLE.test/live?quality=hd&token=old"
    second = "https://example.test/live?token=new&quality=hd"
    assert normalize_stream_url(first) == "https://example.test/live?quality=hd"
    assert stream_url_key(first) == stream_url_key(second)
