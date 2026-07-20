from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class OrderStatus(StrEnum):
    OPEN = "open"
    ASSIGNED = "assigned"
    READY = "ready"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class OrderDraft:
    author_id: int
    author_name: str
    description: str
    quantity: str
    dimensions: str
    model_info: str
    material: str
    color: str
    deadline: str
    budget: str
    building: str = ""
    attachment_file_id: str | None = None
    attachment_type: str | None = None


@dataclass(frozen=True, slots=True)
class Order(OrderDraft):
    id: int = 0
    status: OrderStatus = OrderStatus.OPEN
    created_at: datetime | None = None
    published_chat_id: int | None = None
    published_message_id: int | None = None


@dataclass(frozen=True, slots=True)
class OrderResponse:
    order_id: int
    respondent_id: int
    respondent_name: str
    respondent_username: str | None
    created_at: datetime
    selected_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class OrderSelection:
    order: Order
    selected: OrderResponse
    responses: tuple[OrderResponse, ...]
