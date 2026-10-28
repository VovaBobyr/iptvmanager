from __future__ import annotations

import asyncio
import json
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Channel, HealthCheck


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: str
    method: str
    http_status: int | None = None
    latency_ms: float | None = None
    error_code: str | None = None
    detail: str | None = None


async def _ffprobe(url: str, timeout: float) -> ProbeResult | None:
    executable = shutil.which("ffprobe")
    if not executable:
        return None
    started = time.perf_counter()
    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name",
            "-of",
            "json",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        if "process" in locals():
            process.kill()
            await process.communicate()
        return ProbeResult("uncertain", "ffprobe", error_code="timeout", detail="Probe timed out")
    latency = (time.perf_counter() - started) * 1000
    if process.returncode != 0:
        detail = stderr.decode(errors="replace").strip()[-1000:]
        return ProbeResult(
            "failed",
            "ffprobe",
            latency_ms=latency,
            error_code="probe_failed",
            detail=detail,
        )
    payload = json.loads(stdout or b"{}")
    streams = payload.get("streams", [])
    if streams:
        return ProbeResult(
            "working",
            "ffprobe",
            latency_ms=latency,
            detail=f"{len(streams)} media stream(s)",
        )
    return ProbeResult("uncertain", "ffprobe", latency_ms=latency, error_code="no_streams")


async def _http_probe(
    url: str, client: httpx.AsyncClient, started: float
) -> tuple[ProbeResult, bool]:
    async with client.stream(
        "GET",
        url,
        headers={"User-Agent": "IPTV-Manager/0.1"},
    ) as response:
        latency = (time.perf_counter() - started) * 1000
        if response.status_code == 451:
            return (
                ProbeResult(
                    "geographically_restricted", "http", 451, latency, "legal_restriction"
                ),
                False,
            )
        if response.status_code >= 400:
            return (
                ProbeResult(
                    "failed",
                    "http",
                    response.status_code,
                    latency,
                    f"http_{response.status_code}",
                ),
                False,
            )

        content_type = response.headers.get("content-type", "").casefold()
        async for chunk in response.aiter_bytes(4096):
            if not chunk:
                continue
            looks_like_playlist = (
                "mpegurl" in content_type
                or url.casefold().split("?", 1)[0].endswith((".m3u8", ".m3u"))
                or chunk.lstrip().startswith(b"#EXTM3U")
            )
            return (
                ProbeResult("working", "http", response.status_code, latency),
                looks_like_playlist,
            )

        return (
            ProbeResult("uncertain", "http", response.status_code, latency, "empty_response"),
            False,
        )


async def probe_url(
    url: str, settings: Settings, client: httpx.AsyncClient | None = None
) -> ProbeResult:
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    owned_client = client is None
    client = client or httpx.AsyncClient(follow_redirects=True, timeout=timeout)
    started = time.perf_counter()
    last_error: Exception | None = None
    try:
        for attempt in range(settings.health_retries + 1):
            try:
                http_result, is_playlist = await _http_probe(url, client, started)
                if http_result.status != "working" or not is_playlist:
                    return http_result
                if settings.ffprobe_enabled:
                    ffprobe_result = await _ffprobe(url, settings.request_timeout_seconds)
                    if ffprobe_result is not None:
                        return ffprobe_result
                return http_result
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < settings.health_retries:
                    await asyncio.sleep(0.25 * (attempt + 1))
    finally:
        if owned_client:
            await client.aclose()

    error_code = "timeout" if isinstance(last_error, httpx.TimeoutException) else "network_error"
    return ProbeResult("failed", "http", error_code=error_code, detail=str(last_error))


def save_result(
    session: Session, channel: Channel, result: ProbeResult, runner_name: str = "local"
) -> HealthCheck:
    check = HealthCheck(
        channel_id=channel.id,
        status=result.status,
        method=result.method,
        runner_name=runner_name,
        http_status=result.http_status,
        latency_ms=result.latency_ms,
        error_code=result.error_code,
        detail=result.detail,
        checked_at=datetime.now(UTC),
    )
    channel.health_status = result.status
    session.add(check)
    session.commit()
    session.refresh(check)
    return check
