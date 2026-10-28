import httpx
import pytest

from iptv_manager.config import Settings
from iptv_manager.models import Channel, PlaylistSource
from iptv_manager.services.health import ProbeResult, probe_url, save_result


@pytest.mark.asyncio
async def test_http_probe_marks_response_with_bytes_working() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, content=b"transport stream bytes")
    )
    config = Settings(ffprobe_enabled=False, health_retries=0)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await probe_url("https://stream.test/live.ts", config, client)

    assert result.status == "working"
    assert result.http_status == 200


@pytest.mark.asyncio
async def test_http_451_is_explicit_geographic_restriction() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(451))
    config = Settings(ffprobe_enabled=False, health_retries=0)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await probe_url("https://stream.test/restricted", config, client)

    assert result.status == "geographically_restricted"
    assert result.error_code == "legal_restriction"


def test_saved_health_result_records_runner(session) -> None:
    source = PlaylistSource(name="runner-source", kind="local")
    session.add(source)
    session.flush()
    channel = Channel(
        source_id=source.id,
        stable_key="runner-channel",
        stream_url_key="runner-url",
        name="Runner channel",
        stream_url="https://example.test/live.m3u8",
    )
    session.add(channel)
    session.commit()

    check = save_result(session, channel, ProbeResult("working", "test"), "codespace:test")

    assert check.runner_name == "codespace:test"
