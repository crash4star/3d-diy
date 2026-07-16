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
