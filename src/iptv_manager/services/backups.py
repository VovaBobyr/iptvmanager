from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from ..database import engine

SQLITE_HEADER = b"SQLite format 3\x00"
REQUIRED_TABLES = {"channels", "favorite_groups", "health_scan_jobs", "playlist_sources"}


def sqlite_database_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url == "sqlite:///:memory:":
        raise ValueError(
            "Database backup and restore currently require a file-based SQLite database"
        )
    return Path(database_url.removeprefix(prefix)).resolve()


def _backup_to_path(source_path: Path, destination_path: Path) -> None:
    with closing(sqlite3.connect(source_path)) as source, closing(
        sqlite3.connect(destination_path)
    ) as destination:
        source.backup(destination)


def create_database_backup(database_url: str) -> bytes:
    source_path = sqlite_database_path(database_url)
    if not source_path.exists():
        raise ValueError("The SQLite database does not exist yet")
    source_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="iptv-backup-", suffix=".db", dir=source_path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
        _backup_to_path(source_path, temporary_path)
        return temporary_path.read_bytes()
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _validate_candidate(path: Path) -> None:
    if path.read_bytes()[: len(SQLITE_HEADER)] != SQLITE_HEADER:
        raise ValueError("The selected file is not a SQLite database")
    try:
        with closing(sqlite3.connect(path)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise ValueError("SQLite integrity check failed")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Invalid SQLite backup: {exc}") from exc
    missing = REQUIRED_TABLES - tables
    if missing:
        raise ValueError(f"Backup is missing required tables: {', '.join(sorted(missing))}")


def restore_database_backup(database_url: str, content: bytes) -> Path:
    destination_path = sqlite_database_path(database_url)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path: Path | None = None
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    safety_backup = destination_path.with_name(f"before-restore-{timestamp}.db")
    try:
        with tempfile.NamedTemporaryFile(
            prefix="iptv-restore-", suffix=".db", dir=destination_path.parent, delete=False
        ) as candidate:
            candidate.write(content)
            candidate_path = Path(candidate.name)
        _validate_candidate(candidate_path)
        if destination_path.exists():
            _backup_to_path(destination_path, safety_backup)
            with closing(sqlite3.connect(destination_path)) as current:
                current.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        engine.dispose()
        for suffix in ("-wal", "-shm"):
            Path(f"{destination_path}{suffix}").unlink(missing_ok=True)
        os.replace(candidate_path, destination_path)
        candidate_path = None
        return safety_backup
    finally:
        if candidate_path is not None:
            candidate_path.unlink(missing_ok=True)
