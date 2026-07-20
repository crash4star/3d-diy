from __future__ import annotations

from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .models import Order, OrderDraft, OrderResponse, OrderStatus

RULES_TEXT = """<b>Краткие правила</b>

• Общаемся уважительно и без спама.
• Публикуем только тематические объявления.
• В платном предложении указываем цену или принцип расчёта.
• Не обсуждаем незаконные и опасные изделия.
• Адрес квартиры, телефон, оплату и передачу согласовываем лично.
• По возможности указываем источник и лицензию 3D-модели."""

CREATE_ORDER_BUTTON = "🧩 Создать заявку"
MY_ORDERS_BUTTON = "📋 Мои заявки"
RULES_BUTTON = "📖 Правила"
CANCEL_BUTTON = "❌ Отменить заполнение"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=CREATE_ORDER_BUTTON), KeyboardButton(text=MY_ORDERS_BUTTON)],
            [KeyboardButton(text=RULES_BUTTON), KeyboardButton(text=CANCEL_BUTTON)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие или напишите ответ",
    )


def rules_acceptance_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Правила принимаю",
                    callback_data=f"rules:accept:{user_id}",
                )
            ]
        ]
    )


def format_order(order: Order | OrderDraft, *, preview: bool = False) -> str:
    heading = "🧩 <b>Предпросмотр заявки</b>" if preview else f"🧩 <b>Заявка #{order.id:03d}</b>"
    attachment = "Да" if order.attachment_file_id else "Нет"
    status = "ищет исполнителя"
    if isinstance(order, Order):
        if order.status is OrderStatus.ASSIGNED:
            status = "в работе"
        elif order.status is OrderStatus.READY:
            status = "готово"
        elif order.status is OrderStatus.CLOSED:
            status = "завершено"
    return "\n".join(
        (
            heading,
            "",
            f"<b>Что нужно:</b> {escape(order.description)}",
            f"<b>Количество:</b> {escape(order.quantity)}",
            f"<b>Размеры:</b> {escape(order.dimensions)}",
            f"<b>Модель:</b> {escape(order.model_info)}",
            f"<b>Материал:</b> {escape(order.material)}",
            f"<b>Цвет:</b> {escape(order.color)}",
            f"<b>Срок:</b> {escape(order.deadline)}",
            f"<b>Бюджет:</b> {escape(order.budget)}",
            f"<b>Файл или фото:</b> {attachment}",
            f"<b>Статус:</b> {status}",
        )
    )


def preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Опубликовать", callback_data="draft:publish")],
            [
                InlineKeyboardButton(text="✏️ Заполнить заново", callback_data="draft:restart"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="draft:cancel"),
            ],
        ]
    )


def order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🙋 Откликнуться", callback_data=f"order:respond:{order_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Закрыть заявку", callback_data=f"order:close:{order_id}"
                )
            ],
        ]
    )


def assigned_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📦 Отметить «Готово»", callback_data=f"order:ready:{order_id}"
                )
            ]
        ]
    )


def ready_order_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Завершить заказ", callback_data=f"order:close:{order_id}"
                )
            ]
        ]
    )


def my_orders_keyboard(orders: list[tuple[Order, int]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"👥 #{order.id:03d}: отклики ({response_count})",
                    callback_data=f"order:responses:{order.id}",
                )
            ]
            for order, response_count in orders
        ]
    )


def choose_response_keyboard(order_id: int, respondent_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выбрать исполнителя",
                    callback_data=f"order:select:{order_id}:{respondent_id}",
                )
            ]
        ]
    )


def responses_keyboard(order: Order, responses: list[OrderResponse]) -> InlineKeyboardMarkup | None:
    if order.status is not OrderStatus.OPEN or not responses:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ Выбрать {response.respondent_name[:30]}",
                    callback_data=(f"order:select:{order.id}:{response.respondent_id}"),
                )
            ]
            for response in responses
        ]
    )
