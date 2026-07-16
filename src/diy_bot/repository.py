from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from .models import Order, OrderDraft, OrderStatus

T = TypeVar("T")


class OrderRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    async def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        await self._run(self._initialize_sync)

    async def create(self, draft: OrderDraft) -> Order:
        return await self._run(self._create_sync, draft)

    async def get(self, order_id: int) -> Order | None:
        return await self._run(self._get_sync, order_id)

    async def list_active_by_author(self, author_id: int) -> list[Order]:
        return await self._run(self._list_active_by_author_sync, author_id)

    async def mark_published(self, order_id: int, chat_id: int, message_id: int) -> None:
        await self._run(self._mark_published_sync, order_id, chat_id, message_id)

    async def close(self, order_id: int, author_id: int) -> bool:
        return await self._run(self._close_sync, order_id, author_id)

    async def delete_unpublished(self, order_id: int, author_id: int) -> None:
        await self._run(self._delete_unpublished_sync, order_id, author_id)

    async def _run(self, function: Callable[..., T], *args: Any) -> T:
        return await asyncio.to_thread(function, *args)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER NOT NULL,
                    author_name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    dimensions TEXT NOT NULL,
                    model_info TEXT NOT NULL,
                    material TEXT NOT NULL,
                    color TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    budget TEXT NOT NULL,
                    building TEXT NOT NULL,
                    attachment_file_id TEXT,
                    attachment_type TEXT,
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'closed')),
                    created_at TEXT NOT NULL,
                    published_chat_id INTEGER,
                    published_message_id INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_orders_author_status
                    ON orders(author_id, status);
                """
            )

    def _create_sync(self, draft: OrderDraft) -> Order:
        created_at = datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO orders (
                    author_id, author_name, description, quantity, dimensions,
                    model_info, material, color, deadline, budget, building,
                    attachment_file_id, attachment_type, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.author_id,
                    draft.author_name,
                    draft.description,
                    draft.quantity,
                    draft.dimensions,
                    draft.model_info,
                    draft.material,
                    draft.color,
                    draft.deadline,
                    draft.budget,
                    draft.building,
                    draft.attachment_file_id,
                    draft.attachment_type,
                    OrderStatus.OPEN.value,
                    created_at.isoformat(),
                ),
            )
            order_id = int(cursor.lastrowid or 0)
        return Order(**asdict(draft), id=order_id, status=OrderStatus.OPEN, created_at=created_at)

    def _get_sync(self, order_id: int) -> Order | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return self._row_to_order(row) if row else None

    def _list_active_by_author_sync(self, author_id: int) -> list[Order]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM orders
                WHERE author_id = ? AND status = 'open'
                ORDER BY id DESC
                """,
                (author_id,),
            ).fetchall()
        return [self._row_to_order(row) for row in rows]

    def _mark_published_sync(self, order_id: int, chat_id: int, message_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE orders
                SET published_chat_id = ?, published_message_id = ?
                WHERE id = ?
                """,
                (chat_id, message_id, order_id),
            )

    def _close_sync(self, order_id: int, author_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE orders SET status = 'closed'
                WHERE id = ? AND author_id = ? AND status = 'open'
                """,
                (order_id, author_id),
            )
        return cursor.rowcount == 1

    def _delete_unpublished_sync(self, order_id: int, author_id: int) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM orders
                WHERE id = ? AND author_id = ? AND published_message_id IS NULL
                """,
                (order_id, author_id),
            )

    @staticmethod
    def _row_to_order(row: sqlite3.Row) -> Order:
        return Order(
            id=row["id"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            description=row["description"],
            quantity=row["quantity"],
            dimensions=row["dimensions"],
            model_info=row["model_info"],
            material=row["material"],
            color=row["color"],
            deadline=row["deadline"],
            budget=row["budget"],
            building=row["building"],
            attachment_file_id=row["attachment_file_id"],
            attachment_type=row["attachment_type"],
            status=OrderStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            published_chat_id=row["published_chat_id"],
            published_message_id=row["published_message_id"],
        )
