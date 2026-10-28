from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str = "sqlite:///./data/iptv.db"
    request_timeout_seconds: float = 10.0
    health_concurrency: int = 12
    health_retries: int = 1
    ffprobe_enabled: bool = True
    public_base_url: str = ""
    runner_name: str = "local"

    @classmethod
    def from_env(cls) -> Settings:
        defaults = cls()
        codespace_name = os.getenv("CODESPACE_NAME", "").strip()
        forwarding_domain = os.getenv(
            "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev"
        ).strip()
        detected_public_url = (
            f"https://{codespace_name}-8000.{forwarding_domain}" if codespace_name else ""
        )
        return cls(
            database_url=os.getenv("IPTV_DATABASE_URL", defaults.database_url),
            request_timeout_seconds=float(
                os.getenv("IPTV_REQUEST_TIMEOUT_SECONDS", str(defaults.request_timeout_seconds))
            ),
            health_concurrency=int(
                os.getenv("IPTV_HEALTH_CONCURRENCY", str(defaults.health_concurrency))
            ),
            health_retries=int(os.getenv("IPTV_HEALTH_RETRIES", str(defaults.health_retries))),
            ffprobe_enabled=_as_bool(
                os.getenv("IPTV_FFPROBE_ENABLED", str(defaults.ffprobe_enabled))
            ),
            public_base_url=os.getenv(
                "IPTV_PUBLIC_BASE_URL", detected_public_url or defaults.public_base_url
            ).rstrip("/"),
            runner_name=os.getenv(
                "IPTV_RUNNER_NAME", f"codespace:{codespace_name}" if codespace_name else "local"
            ).strip()
            or defaults.runner_name,
        )


settings = Settings.from_env()
