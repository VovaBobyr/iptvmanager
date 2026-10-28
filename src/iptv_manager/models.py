from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class PlaylistSource(Base):
    __tablename__ = "playlist_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(20), default="remote")
    url: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(200))

    channels: Mapped[list[Channel]] = relationship(back_populates="source")


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("source_id", "stable_key", name="uq_channel_source_stable_key"),
        Index("ix_channels_filtering", "active", "country", "language", "group_title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("playlist_sources.id"), index=True)
    stable_key: Mapped[str] = mapped_column(String(64))
    stream_url_key: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    stream_url: Mapped[str] = mapped_column(Text)
    tvg_id: Mapped[str | None] = mapped_column(String(300), index=True)
    tvg_name: Mapped[str | None] = mapped_column(String(500))
    tvg_logo: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(20), index=True)
    language: Mapped[str | None] = mapped_column(String(100), index=True)
    group_title: Mapped[str | None] = mapped_column(String(300), index=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    health_status: Mapped[str] = mapped_column(String(30), default="unknown", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    source: Mapped[PlaylistSource] = relationship(back_populates="channels")
    checks: Mapped[list[HealthCheck]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class FavoriteGroup(Base):
    __tablename__ = "favorite_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    items: Mapped[list[FavoriteItem]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="FavoriteItem.position",
    )


class FavoriteItem(Base):
    __tablename__ = "favorite_items"
    __table_args__ = (UniqueConstraint("group_id", "channel_id", name="uq_favorite_channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("favorite_groups.id", ondelete="CASCADE"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    custom_name: Mapped[str | None] = mapped_column(String(500))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    group: Mapped[FavoriteGroup] = relationship(back_populates="items")
    channel: Mapped[Channel] = relationship()


class HealthCheck(Base):
    __tablename__ = "health_checks"
    __table_args__ = (Index("ix_health_channel_checked", "channel_id", "checked_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), index=True)
    method: Mapped[str] = mapped_column(String(30))
    runner_name: Mapped[str] = mapped_column(String(120), default="local")
    http_status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(100))
    detail: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    channel: Mapped[Channel] = relationship(back_populates="checks")


class HealthScanJob(Base):
    __tablename__ = "health_scan_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("playlist_sources.id"), index=True)
    favorites_only: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[int] = mapped_column(Integer, default=0)
    working: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    uncertain: Mapped[int] = mapped_column(Integer, default=0)
    geographically_restricted: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
