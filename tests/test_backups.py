from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from iptv_manager.services.backups import create_database_backup, restore_database_backup


def _create_database(path, marker: str) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for table in ("channels", "favorite_groups", "health_scan_jobs", "playlist_sources"):
            connection.execute(f"CREATE TABLE {table} (value TEXT)")
        connection.execute("INSERT INTO channels VALUES (?)", (marker,))
        connection.commit()


def test_backup_and_restore_round_trip(tmp_path):
    current_path = tmp_path / "current.db"
    imported_path = tmp_path / "imported.db"
    _create_database(current_path, "current")
    _create_database(imported_path, "imported")
    imported_content = create_database_backup(f"sqlite:///{imported_path}")

    safety_backup = restore_database_backup(f"sqlite:///{current_path}", imported_content)

    with closing(sqlite3.connect(current_path)) as connection:
        assert connection.execute("SELECT value FROM channels").fetchone()[0] == "imported"
    with closing(sqlite3.connect(safety_backup)) as connection:
        assert connection.execute("SELECT value FROM channels").fetchone()[0] == "current"


def test_restore_rejects_non_sqlite_file(tmp_path):
    current_path = tmp_path / "current.db"
    _create_database(current_path, "current")

    with pytest.raises(ValueError, match="not a SQLite database"):
        restore_database_backup(f"sqlite:///{current_path}", b"not a database")
