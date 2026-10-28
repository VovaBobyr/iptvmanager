from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_SPACE_RE = re.compile(r"\s+")
_VOLATILE_QUERY_KEYS = {"token", "auth", "signature", "sig", "expires", "exp"}


def normalize_text(value: str | None) -> str:
    return _SPACE_RE.sub(" ", (value or "").strip().casefold())


def normalize_stream_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in _VOLATILE_QUERY_KEYS
    ]
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), parts.path, urlencode(sorted(query)), "")
    )


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def channel_stable_key(metadata: dict[str, str], name: str, stream_url: str) -> str:
    tvg_id = normalize_text(metadata.get("tvg-id"))
    if tvg_id:
        return sha256(f"tvg-id:{tvg_id}")

    identity_fields = (
        normalize_text(metadata.get("tvg-name") or name),
        normalize_text(metadata.get("tvg-country") or metadata.get("country")),
        normalize_text(metadata.get("tvg-language") or metadata.get("language")),
        normalize_text(metadata.get("group-title")),
    )
    if any(identity_fields[1:]):
        return sha256("metadata:" + "|".join(identity_fields))
    return sha256("url:" + normalize_stream_url(stream_url))


def stream_url_key(url: str) -> str:
    return sha256(normalize_stream_url(url))
