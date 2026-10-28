from __future__ import annotations

import re
from dataclasses import dataclass, field

_ATTRIBUTE_RE = re.compile(r'([\w-]+)="([^"]*)"|([\w-]+)=([^\s,]+)')


@dataclass(slots=True)
class M3UEntry:
    name: str
    url: str
    metadata: dict[str, str] = field(default_factory=dict)


def _parse_extinf(line: str) -> tuple[str, dict[str, str]]:
    body = line.partition(":")[2]
    info, separator, name = body.rpartition(",")
    if not separator:
        info, name = body, "Unnamed channel"
    metadata: dict[str, str] = {}
    for match in _ATTRIBUTE_RE.finditer(info):
        key = match.group(1) or match.group(3)
        value = match.group(2) if match.group(1) else match.group(4)
        metadata[key.casefold()] = value
    return name.strip() or metadata.get("tvg-name", "Unnamed channel"), metadata


def parse_m3u(content: str) -> list[M3UEntry]:
    entries: list[M3UEntry] = []
    pending: tuple[str, dict[str, str]] | None = None

    for raw_line in content.lstrip("\ufeff").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("#EXTINF:"):
            pending = _parse_extinf(line)
            continue
        if line.startswith("#"):
            continue
        if pending is None:
            pending = (line.rsplit("/", 1)[-1] or "Unnamed channel", {})
        name, metadata = pending
        entries.append(M3UEntry(name=name, url=line, metadata=metadata))
        pending = None

    return entries


def _escape_attribute(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "\\\"")


def render_m3u(entries: list[M3UEntry]) -> str:
    lines = ["#EXTM3U"]
    preferred = ("tvg-id", "tvg-name", "tvg-logo", "tvg-country", "tvg-language", "group-title")
    for entry in entries:
        attributes = " ".join(
            f'{key}="{_escape_attribute(entry.metadata[key])}"'
            for key in preferred
            if entry.metadata.get(key)
        )
        prefix = f"#EXTINF:-1 {attributes}" if attributes else "#EXTINF:-1"
        lines.extend((f"{prefix},{entry.name}", entry.url))
    return "\n".join(lines) + "\n"
