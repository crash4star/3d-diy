from dataclasses import dataclass, field
from pathlib import Path

import pytest

from diy_bot.handlers import (
    close_order,
    mark_order_ready,
    respond_to_order,
    select_order_response,
)
from diy_bot.models import OrderDraft, OrderStatus
from diy_bot.repository import OrderRepository


@dataclass
class FakeUser:
    id: int
    full_name: str
    username: str | None = None


@dataclass
class FakeCallback:
    data: str
    from_user: FakeUser
    message: object | None = None
    answers: list[tuple[str | None, bool]] = field(default_factory=list)

    async def answer(self, text: str | None = None, *, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


@dataclass
class FakeBot:
    messages: list[tuple[int, str, object | None]] = field(default_factory=list)
    edits: list[tuple[int, int, str, object | None]] = field(default_factory=list)

    async def send_message(
        self, chat_id: int, text: str, *, reply_markup: object | None = None
    ) -> None:
        self.messages.append((chat_id, text, reply_markup))

    async def edit_message_text(
        self,
        text: str,
        *,
        chat_id: int,
        message_id: int,
        reply_markup: object | None = None,
    ) -> None:
        self.edits.append((chat_id, message_id, text, reply_markup))


def make_draft() -> OrderDraft:
    return OrderDraft(
        author_id=42,
        author_name="Заказчик",
        description="Тестовая деталь",
        quantity="1",
        dimensions="10 × 10 мм",
        model_info="Модель есть",
        material="PETG",
        color="Чёрный",
        deadline="На этой неделе",
        budget="500 ₽",
    )


@pytest.mark.asyncio
async def test_multiple_responses_do_not_change_order_status(tmp_path: Path) -> None:
    repository = OrderRepository(tmp_path / "bot.db")
    await repository.initialize()
    order = await repository.create(make_draft())
    bot = FakeBot()

    callbacks = [
        FakeCallback(
            data=f"order:respond:{order.id}",
            from_user=FakeUser(id=100, full_name="Первый исполнитель", username="first"),
        ),
        FakeCallback(
            data=f"order:respond:{order.id}",
            from_user=FakeUser(id=101, full_name="Второй исполнитель", username="second"),
        ),
    ]

    for callback in callbacks:
        await respond_to_order(callback, bot, repository)  # type: ignore[arg-type]

    stored = await repository.get(order.id)
    assert stored is not None
    assert stored.status is OrderStatus.OPEN
    assert [callback.answers for callback in callbacks] == [
        [("Отклик отправлен автору", True)],
        [("Отклик отправлен автору", True)],
    ]
    assert [chat_id for chat_id, _, _ in bot.messages] == [42, 42]
    assert "Первый исполнитель" in bot.messages[0][1]
    assert "Второй исполнитель" in bot.messages[1][1]


@pytest.mark.asyncio
async def test_author_selects_one_response_and_everyone_is_notified(tmp_path: Path) -> None:
    repository = OrderRepository(tmp_path / "bot.db")
    await repository.initialize()
    order = await repository.create(make_draft())
    await repository.mark_published(order.id, -1004491175805, 500)
    await repository.add_response(order.id, 100, "Первый исполнитель", "first")
    await repository.add_response(order.id, 101, "Второй исполнитель", "second")
    callback = FakeCallback(
        data=f"order:select:{order.id}:101",
        from_user=FakeUser(id=42, full_name="Заказчик"),
    )
    bot = FakeBot()

    await select_order_response(callback, bot, repository)  # type: ignore[arg-type]

    stored = await repository.get(order.id)
    assert stored is not None
    assert stored.status is OrderStatus.ASSIGNED
    assert callback.answers == [("Исполнитель выбран", True)]
    assert [chat_id for chat_id, _, _ in bot.messages] == [100, 101]
    assert "другого исполнителя" in bot.messages[0][1]
    assert "выбрал вас" in bot.messages[1][1]
    assert len(bot.edits) == 1
    assert bot.edits[0][0:2] == (-1004491175805, 500)
    assert "в работе" in bot.edits[0][2]

    ready_callback = FakeCallback(
        data=f"order:ready:{order.id}",
        from_user=FakeUser(id=101, full_name="Второй исполнитель"),
    )
    await mark_order_ready(ready_callback, bot, repository)  # type: ignore[arg-type]
    ready_order = await repository.get(order.id)
    assert ready_order is not None
    assert ready_order.status is OrderStatus.READY
    assert ready_callback.answers == [("Заказ отмечен как готовый", True)]
    assert "готово" in bot.edits[-1][2]

    close_callback = FakeCallback(
        data=f"order:close:{order.id}",
        from_user=FakeUser(id=42, full_name="Заказчик"),
    )
    await close_order(close_callback, bot, repository)  # type: ignore[arg-type]
    closed_order = await repository.get(order.id)
    assert closed_order is not None
    assert closed_order.status is OrderStatus.CLOSED
    assert close_callback.answers == [("Заказ завершён", False)]
    assert "завершено" in bot.edits[-1][2]
    assert "Спасибо за работу" in bot.messages[-1][1]
