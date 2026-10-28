from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str | None = None
    kind: str = "remote"


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    kind: str
    url: str | None
    enabled: bool
    refreshed_at: datetime | None


class InlineImport(BaseModel):
    source_name: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class ChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    name: str
    stream_url: str
    tvg_id: str | None
    tvg_logo: str | None
    country: str | None
    language: str | None
    group_title: str | None
    active: bool
    health_status: str


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class FavoriteAdd(BaseModel):
    channel_id: int


class ReorderFavorites(BaseModel):
    channel_ids: list[int]


class HealthScanCreate(BaseModel):
    source_id: int | None = None
    favorites_only: bool = False
