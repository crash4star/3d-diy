from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

BACKUP_PATTERN = "bot-*.sqlite3"


def create_backup(
    database_path: Path,
    backup_directory: Path,
    retention_count: int,
    *,
    created_at: datetime | None = None,
) -> Path:
    if retention_count < 1:
        raise ValueError("Количество резервных копий должно быть положительным")
    if not database_path.is_file():
        raise FileNotFoundError(f"База данных не найдена: {database_path}")

    backup_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(backup_directory, 0o700)
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    filename = f"bot-{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.sqlite3"
    destination = backup_directory / filename
    temporary = backup_directory / f".{filename}.tmp"

    try:
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(temporary)) as target,
        ):
            source.backup(target)

        with closing(sqlite3.connect(temporary)) as backup:
            result = backup.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise RuntimeError(f"Проверка целостности не пройдена: {result!r}")

        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
        _prune_backups(backup_directory, retention_count)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def _prune_backups(backup_directory: Path, retention_count: int) -> None:
    backups = sorted(backup_directory.glob(BACKUP_PATTERN), reverse=True)
    for expired in backups[retention_count:]:
        expired.unlink()


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError("BACKUP_RETENTION_COUNT должен быть целым числом") from error
    if parsed < 1:
        raise ValueError("BACKUP_RETENTION_COUNT должен быть больше нуля")
    return parsed


def run() -> None:
    try:
        database_path = Path(os.getenv("DATABASE_PATH", "data/bot.db"))
        backup_directory = Path(os.getenv("BACKUP_DIR", "data/backups"))
        retention_count = _positive_int(os.getenv("BACKUP_RETENTION_COUNT", "14"))
        backup_path = create_backup(database_path, backup_directory, retention_count)
    except (OSError, sqlite3.Error, RuntimeError, ValueError) as error:
        print(f"Backup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"Backup created and verified: {backup_path}")


if __name__ == "__main__":
    run()
