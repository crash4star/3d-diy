import sqlite3
from pathlib import Path

import pytest

from diy_bot.models import OrderDraft, OrderStatus
from diy_bot.repository import OrderRepository


def make_draft(author_id: int = 42) -> OrderDraft:
    return OrderDraft(
        author_id=author_id,
        author_name="Иван",
        description="Крепление датчика",
        quantity="2",
        dimensions="45 × 30 мм",
        model_info="STL приложен",
        material="PETG",
        color="Белый",
        deadline="До выходных",
        budget="Материалы + 300 ₽",
        building="2",
        attachment_file_id="file-id",
        attachment_type="document",
    )


@pytest.mark.asyncio
async def test_order_lifecycle(tmp_path: Path) -> None:
    repository = OrderRepository(tmp_path / "bot.db")
    await repository.initialize()

    created = await repository.create(make_draft())
    assert created.id == 1
    assert created.status is OrderStatus.OPEN

    await repository.mark_published(created.id, -1001, 50)
    stored = await repository.get(created.id)
    assert stored is not None
    assert stored.published_chat_id == -1001
    assert stored.published_message_id == 50

    active = await repository.list_active_by_author(42)
    assert [order.id for order in active] == [created.id]

    assert await repository.close(created.id, author_id=7) is False
    assert await repository.close(created.id, author_id=42) is True
    assert await repository.list_active_by_author(42) == []


@pytest.mark.asyncio
async def test_only_unpublished_order_can_be_deleted(tmp_path: Path) -> None:
    repository = OrderRepository(tmp_path / "bot.db")
    await repository.initialize()
    unpublished = await repository.create(make_draft())
    published = await repository.create(make_draft())
    await repository.mark_published(published.id, -1001, 51)

    await repository.delete_unpublished(unpublished.id, 42)
    await repository.delete_unpublished(published.id, 42)

    assert await repository.get(unpublished.id) is None
    assert await repository.get(published.id) is not None


@pytest.mark.asyncio
async def test_response_selection_is_unique_and_atomic(tmp_path: Path) -> None:
    repository = OrderRepository(tmp_path / "bot.db")
    await repository.initialize()
    order = await repository.create(make_draft())
    await repository.mark_published(order.id, -1001, 52)

    assert await repository.add_response(order.id, 100, "Первый", "first") is True
    assert await repository.add_response(order.id, 100, "Первый", "first") is False
    assert await repository.add_response(order.id, 101, "Второй", None) is True
    first_work = await repository.list_work_by_respondent(100)
    assert [item.order.id for item in first_work] == [order.id]
    assert first_work[0].response.selected_at is None

    selection = await repository.select_response(order.id, author_id=42, respondent_id=101)
    assert selection is not None
    assert selection.order.status is OrderStatus.ASSIGNED
    assert selection.selected.respondent_id == 101
    assert [response.respondent_id for response in selection.responses] == [100, 101]
    assert selection.responses[0].selected_at is None
    assert selection.responses[1].selected_at is not None
    selected_work = await repository.list_work_by_respondent(101)
    assert selected_work[0].order.status is OrderStatus.ASSIGNED
    assert selected_work[0].response.selected_at is not None

    assert await repository.select_response(order.id, author_id=42, respondent_id=100) is None
    assert await repository.add_response(order.id, 102, "Третий", None) is False
    assert [item.id for item in await repository.list_active_by_author(42)] == [order.id]
    assert await repository.close(order.id, author_id=42) is False
    assert await repository.mark_ready(order.id, respondent_id=100) is None
    ready = await repository.mark_ready(order.id, respondent_id=101)
    assert ready is not None
    assert ready.status is OrderStatus.READY
    assert await repository.close(order.id, author_id=42) is True


@pytest.mark.asyncio
async def test_existing_database_is_migrated_for_assigned_status(tmp_path: Path) -> None:
    database_path = tmp_path / "bot.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE orders (
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
                    CHECK (status IN ('open', 'assigned', 'closed')),
                created_at TEXT NOT NULL,
                published_chat_id INTEGER,
                published_message_id INTEGER
            );
            CREATE TABLE order_responses (
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                respondent_id INTEGER NOT NULL,
                respondent_name TEXT NOT NULL,
                respondent_username TEXT,
                created_at TEXT NOT NULL,
                selected_at TEXT,
                PRIMARY KEY (order_id, respondent_id)
            );
            """
        )
    repository = OrderRepository(database_path)
    legacy_order = await repository.create(make_draft())
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO order_responses (
                order_id, respondent_id, respondent_name, respondent_username,
                created_at, selected_at
            ) VALUES (?, 100, 'Исполнитель', 'maker', '2026-07-20T10:00:00+00:00', NULL)
            """,
            (legacy_order.id,),
        )
    await repository.initialize()
    order = await repository.get(legacy_order.id)

    assert order is not None
    assert order.description == legacy_order.description
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    responses = await repository.list_responses(order.id)
    assert [(response.respondent_id, response.respondent_username) for response in responses] == [
        (100, "maker")
    ]
    selection = await repository.select_response(order.id, author_id=42, respondent_id=100)

    assert selection is not None
    assert selection.order.status is OrderStatus.ASSIGNED
