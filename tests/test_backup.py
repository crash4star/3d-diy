import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from diy_bot.backup import create_backup


def create_database(path: Path, value: str = "saved") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute("INSERT INTO example (value) VALUES (?)", (value,))


def test_backup_is_valid_and_private(tmp_path: Path) -> None:
    database_path = tmp_path / "bot.db"
    backup_directory = tmp_path / "backups"
    create_database(database_path)

    backup_path = create_backup(database_path, backup_directory, retention_count=14)

    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT value FROM example").fetchone() == ("saved",)
    assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup_directory.stat().st_mode) == 0o700


def test_backup_rotation_keeps_newest_files(tmp_path: Path) -> None:
    database_path = tmp_path / "bot.db"
    backup_directory = tmp_path / "backups"
    create_database(database_path)

    for day in (1, 2, 3):
        create_backup(
            database_path,
            backup_directory,
            retention_count=2,
            created_at=datetime(2026, 7, day, tzinfo=UTC),
        )

    assert [path.name for path in sorted(backup_directory.glob("bot-*.sqlite3"))] == [
        "bot-20260702T000000000000Z.sqlite3",
        "bot-20260703T000000000000Z.sqlite3",
    ]


def test_missing_database_does_not_create_empty_backup(tmp_path: Path) -> None:
    backup_directory = tmp_path / "backups"

    with pytest.raises(FileNotFoundError):
        create_backup(tmp_path / "missing.db", backup_directory, retention_count=14)

    assert not backup_directory.exists()


@pytest.mark.parametrize("retention_count", [0, -1])
def test_retention_count_must_be_positive(tmp_path: Path, retention_count: int) -> None:
    database_path = tmp_path / "bot.db"
    create_database(database_path)

    with pytest.raises(ValueError):
        create_backup(database_path, tmp_path / "backups", retention_count)
