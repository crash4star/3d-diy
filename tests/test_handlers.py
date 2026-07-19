from dataclasses import dataclass, field
from pathlib import Path

import pytest

from diy_bot.handlers import respond_to_order
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
    answers: list[tuple[str | None, bool]] = field(default_factory=list)

    async def answer(self, text: str | None = None, *, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


@dataclass
class FakeBot:
    messages: list[tuple[int, str]] = field(default_factory=list)

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


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
    assert [chat_id for chat_id, _ in bot.messages] == [42, 42]
    assert "Первый исполнитель" in bot.messages[0][1]
    assert "Второй исполнитель" in bot.messages[1][1]
