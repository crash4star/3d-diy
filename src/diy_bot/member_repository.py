from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path


class MemberRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._initialize_sync)

    async def accept_rules(self, chat_id: int, user_id: int, display_name: str) -> bool:
        return await asyncio.to_thread(self._accept_rules_sync, chat_id, user_id, display_name)

    async def has_accepted_rules(self, chat_id: int, user_id: int) -> bool:
        return await asyncio.to_thread(self._has_accepted_rules_sync, chat_id, user_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS member_rule_acceptances (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    display_name TEXT NOT NULL,
                    accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, user_id)
                )
                """
            )

    def _accept_rules_sync(self, chat_id: int, user_id: int, display_name: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO member_rule_acceptances (
                    chat_id, user_id, display_name
                ) VALUES (?, ?, ?)
                """,
                (chat_id, user_id, display_name),
            )
        return cursor.rowcount == 1

    def _has_accepted_rules_sync(self, chat_id: int, user_id: int) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM member_rule_acceptances
                WHERE chat_id = ? AND user_id = ?
                """,
                (chat_id, user_id),
            ).fetchone()
        return row is not None
