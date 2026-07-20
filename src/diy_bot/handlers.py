from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.enums import ChatType, ContentType
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import Settings
from .member_repository import MemberRepository
from .models import Order, OrderDraft, OrderStatus
from .presentation import (
    CANCEL_BUTTON,
    CREATE_ORDER_BUTTON,
    MY_ORDERS_BUTTON,
    RULES_BUTTON,
    RULES_TEXT,
    assigned_order_keyboard,
    choose_response_keyboard,
    format_order,
    main_menu_keyboard,
    my_orders_keyboard,
    order_keyboard,
    preview_keyboard,
    responses_keyboard,
    rules_acceptance_keyboard,
)
from .repository import OrderRepository
from .states import OrderForm

logger = logging.getLogger(__name__)
router = Router(name=__name__)

WELCOME_TEXT = """Привет! Я помогаю жителям создавать заявки на 3D-печать.

Выберите нужное действие кнопками внизу экрана."""

QUESTIONS = {
    OrderForm.description: "Что нужно напечатать? Опишите деталь и её назначение.",
    OrderForm.quantity: "Какое количество нужно?",
    OrderForm.dimensions: "Укажите размеры или напишите «не знаю».",
    OrderForm.model: (
        "Пришлите STL/другой файл, фотографию, ссылку или опишите, нужна ли разработка модели."
    ),
    OrderForm.material: "Какой материал нужен? Например, PLA или PETG. Можно написать «на выбор».",
    OrderForm.color: "Какой цвет нужен?",
    OrderForm.deadline: "Когда деталь должна быть готова?",
    OrderForm.budget: "Укажите бюджет, принцип расчёта или вариант обмена.",
}

NEW_MEMBER_RULES_TEXT = """Добро пожаловать, {member_link}!

Перед участием подтвердите краткие правила:
• общаемся уважительно и без спама;
• публикуем только тематические объявления;
• не обсуждаем незаконные и опасные изделия;
• личные данные и оплату согласовываем в личных сообщениях.

Нажмите кнопку ниже, если принимаете правила."""


def _text(message: Message, *, max_length: int = 500) -> str | None:
    value = (message.text or "").strip()
    if not value or len(value) > max_length:
        return None
    return value


async def _save_text_and_ask(
    message: Message,
    state: FSMContext,
    *,
    key: str,
    next_state: OrderForm,
    max_length: int = 500,
) -> None:
    value = _text(message, max_length=max_length)
    if value is None:
        await message.answer(f"Нужен текст длиной от 1 до {max_length} символов.")
        return
    await state.update_data(**{key: value})
    await state.set_state(next_state)
    await message.answer(QUESTIONS[next_state])


async def _begin_order(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(OrderForm.description)
    await message.answer(QUESTIONS[OrderForm.description])


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())
    parts = (message.text or "").split(maxsplit=1)
    if message.chat.type == ChatType.PRIVATE and len(parts) == 2 and parts[1] == "order":
        await _begin_order(message, state)


@router.message(F.new_chat_members)
async def welcome_new_members(message: Message, member_repository: MemberRepository) -> None:
    for member in message.new_chat_members or []:
        if member.is_bot:
            continue
        member_link = f'<a href="tg://user?id={member.id}">{escape(member.full_name)}</a>'
        if await member_repository.has_accepted_rules(message.chat.id, member.id):
            await message.answer(f"С возвращением, {member_link}! Правила уже приняты.")
            continue
        await message.answer(
            NEW_MEMBER_RULES_TEXT.format(member_link=member_link),
            reply_markup=rules_acceptance_keyboard(member.id),
        )


@router.callback_query(F.data.startswith("rules:accept:"))
async def accept_group_rules(callback: CallbackQuery, member_repository: MemberRepository) -> None:
    expected_user_id = _callback_user_id(callback.data)
    if expected_user_id is None:
        await callback.answer("Некорректная кнопка", show_alert=True)
        return
    if callback.from_user.id != expected_user_id:
        await callback.answer("Эта кнопка предназначена другому участнику", show_alert=True)
        return
    if callback.message is None:
        await callback.answer("Сообщение уже недоступно", show_alert=True)
        return

    created = await member_repository.accept_rules(
        callback.message.chat.id,
        callback.from_user.id,
        callback.from_user.full_name,
    )
    await callback.answer("Правила приняты" if created else "Вы уже приняли правила")
    await callback.message.edit_text(
        f"✅ {escape(callback.from_user.full_name)}, правила приняты. Добро пожаловать!",
        reply_markup=None,
    )


@router.message(Command("rules"))
@router.message(F.text == RULES_BUTTON)
async def rules(message: Message) -> None:
    await message.answer(RULES_TEXT)


@router.message(Command("where"))
async def where(message: Message) -> None:
    topic_id = message.message_thread_id or 0
    await message.answer(
        "<b>Параметры текущего места:</b>\n"
        f"TARGET_CHAT_ID=<code>{message.chat.id}</code>\n"
        f"ORDERS_TOPIC_ID=<code>{topic_id}</code>"
    )


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_BUTTON)
async def cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Сейчас нет активной формы.")
        return
    await state.clear()
    await message.answer("Заполнение заявки отменено.")


@router.message(Command("order"))
@router.message(F.text == CREATE_ORDER_BUTTON)
async def order_start(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user is None:
        return
    if message.chat.type == ChatType.PRIVATE:
        await _begin_order(message, state)
        return

    await state.clear()
    bot_user = await bot.me()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧩 Открыть личную форму",
                    url=f"https://t.me/{bot_user.username}?start=order",
                )
            ]
        ]
    )
    await message.answer(
        "Заявка заполняется в личном чате, чтобы ответы не попадали в общий разговор.",
        reply_markup=keyboard,
    )


@router.message(OrderForm.description)
async def order_description(message: Message, state: FSMContext) -> None:
    await _save_text_and_ask(
        message, state, key="description", next_state=OrderForm.quantity, max_length=500
    )


@router.message(OrderForm.quantity)
async def order_quantity(message: Message, state: FSMContext) -> None:
    await _save_text_and_ask(
        message, state, key="quantity", next_state=OrderForm.dimensions, max_length=100
    )


@router.message(OrderForm.dimensions)
async def order_dimensions(message: Message, state: FSMContext) -> None:
    await _save_text_and_ask(
        message, state, key="dimensions", next_state=OrderForm.model, max_length=200
    )


@router.message(
    OrderForm.model, F.content_type.in_({ContentType.TEXT, ContentType.DOCUMENT, ContentType.PHOTO})
)
async def order_model(message: Message, state: FSMContext) -> None:
    data: dict[str, str | None] = {"attachment_file_id": None, "attachment_type": None}
    if message.document:
        data.update(
            model_info=(message.caption or message.document.file_name or "Файл приложен")[:500],
            attachment_file_id=message.document.file_id,
            attachment_type="document",
        )
    elif message.photo:
        data.update(
            model_info=(message.caption or "Фотография приложена")[:500],
            attachment_file_id=message.photo[-1].file_id,
            attachment_type="photo",
        )
    else:
        value = _text(message)
        if value is None:
            await message.answer("Пришлите текст, документ или фотографию.")
            return
        data["model_info"] = value
    await state.update_data(**data)
    await state.set_state(OrderForm.material)
    await message.answer(QUESTIONS[OrderForm.material])


@router.message(OrderForm.model)
async def order_model_invalid(message: Message) -> None:
    await message.answer("Поддерживаются текст, документ или фотография.")


@router.message(OrderForm.material)
async def order_material(message: Message, state: FSMContext) -> None:
    await _save_text_and_ask(
        message, state, key="material", next_state=OrderForm.color, max_length=100
    )


@router.message(OrderForm.color)
async def order_color(message: Message, state: FSMContext) -> None:
    await _save_text_and_ask(
        message, state, key="color", next_state=OrderForm.deadline, max_length=100
    )


@router.message(OrderForm.deadline)
async def order_deadline(message: Message, state: FSMContext) -> None:
    await _save_text_and_ask(
        message, state, key="deadline", next_state=OrderForm.budget, max_length=100
    )


@router.message(OrderForm.budget)
async def order_budget(message: Message, state: FSMContext) -> None:
    if message.from_user is None:
        return
    value = _text(message, max_length=200)
    if value is None:
        await message.answer("Укажите бюджет текстом, не более 200 символов.")
        return
    await state.update_data(budget=value)
    data = await state.get_data()
    draft = _draft_from_data(message, data)
    await state.set_state(OrderForm.preview)
    await message.answer(format_order(draft, preview=True), reply_markup=preview_keyboard())


@router.callback_query(OrderForm.preview, F.data == "draft:restart")
async def draft_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await state.set_state(OrderForm.description)
    if callback.message:
        await callback.message.answer(QUESTIONS[OrderForm.description])


@router.callback_query(OrderForm.preview, F.data == "draft:cancel")
async def draft_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Заявка отменена")
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(OrderForm.preview, F.data == "draft:publish")
async def draft_publish(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    repository: OrderRepository,
    settings: Settings,
) -> None:
    await callback.answer()
    if callback.from_user is None:
        return
    if settings.target_chat_id == 0:
        if callback.message:
            await callback.message.answer(
                "Публикация ещё не настроена: укажите TARGET_CHAT_ID в .env."
            )
        return
    data = await state.get_data()
    draft = _draft_from_callback(callback, data)
    order = await repository.create(draft)
    try:
        published = await _publish_order(bot, settings, order)
    except TelegramAPIError as error:
        await repository.delete_unpublished(order.id, order.author_id)
        logger.warning("Не удалось опубликовать заявку %s: %s", order.id, error)
        if callback.message:
            await callback.message.answer(
                "Не удалось опубликовать заявку. Проверьте настройки группы, темы и права бота."
            )
        return
    await repository.mark_published(order.id, published.chat.id, published.message_id)
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(f"Заявка #{order.id:03d} опубликована.")


@router.message(Command("myorders"))
@router.message(F.text == MY_ORDERS_BUTTON)
async def my_orders(message: Message, repository: OrderRepository) -> None:
    if message.from_user is None:
        return
    orders = await repository.list_active_by_author(message.from_user.id)
    if not orders:
        await message.answer("У вас нет активных заявок.")
        return
    orders_with_counts = [
        (order, len(await repository.list_responses(order.id))) for order in orders
    ]
    lines = ["<b>Ваши активные заявки:</b>"]
    lines.extend(f"#{order.id:03d} — {escape(order.description[:80])}" for order in orders)
    await message.answer("\n".join(lines), reply_markup=my_orders_keyboard(orders_with_counts))


@router.callback_query(F.data.startswith("order:respond:"))
async def respond_to_order(callback: CallbackQuery, bot: Bot, repository: OrderRepository) -> None:
    order_id = _callback_order_id(callback.data)
    if order_id is None:
        await callback.answer("Некорректный номер заявки", show_alert=True)
        return
    order = await repository.get(order_id)
    if order is None or order.status is not OrderStatus.OPEN:
        await callback.answer("Заявка уже закрыта или не найдена", show_alert=True)
        return
    if callback.from_user.id == order.author_id:
        await callback.answer("Это ваша заявка", show_alert=True)
        return
    respondent = callback.from_user
    if not await repository.add_response(
        order.id,
        respondent.id,
        respondent.full_name,
        respondent.username,
    ):
        await callback.answer(
            "Вы уже откликнулись или заявка больше не принимает отклики", show_alert=True
        )
        return
    username = f"@{escape(respondent.username)}" if respondent.username else "без username"
    try:
        await bot.send_message(
            order.author_id,
            f"На заявку #{order.id:03d} откликнулся "
            f'<a href="tg://user?id={respondent.id}">{escape(respondent.full_name)}</a> '
            f"({username}).",
            reply_markup=choose_response_keyboard(order.id, respondent.id),
        )
    except TelegramAPIError:
        await callback.answer(
            "Отклик сохранён. Автор увидит его в разделе «Мои заявки».", show_alert=True
        )
        return
    await callback.answer("Отклик отправлен автору", show_alert=True)


@router.callback_query(F.data.startswith("order:responses:"))
async def show_order_responses(callback: CallbackQuery, repository: OrderRepository) -> None:
    order_id = _callback_order_id(callback.data)
    if order_id is None:
        await callback.answer("Некорректный номер заявки", show_alert=True)
        return
    order = await repository.get(order_id)
    if order is None or callback.from_user.id != order.author_id:
        await callback.answer("Эта заявка вам недоступна", show_alert=True)
        return
    responses = await repository.list_responses(order_id)
    if not responses:
        await callback.answer("На заявку пока никто не откликнулся", show_alert=True)
        return
    lines = [f"<b>Отклики на заявку #{order.id:03d}:</b>"]
    for response in responses:
        username = (
            f"@{escape(response.respondent_username)}"
            if response.respondent_username
            else "без username"
        )
        marker = " — выбран" if response.selected_at else ""
        lines.append(
            f'• <a href="tg://user?id={response.respondent_id}">'
            f"{escape(response.respondent_name)}</a> ({username}){marker}"
        )
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "\n".join(lines), reply_markup=responses_keyboard(order, responses)
        )


@router.callback_query(F.data.startswith("order:select:"))
async def select_order_response(
    callback: CallbackQuery, bot: Bot, repository: OrderRepository
) -> None:
    ids = _callback_selection_ids(callback.data)
    if ids is None:
        await callback.answer("Некорректные данные отклика", show_alert=True)
        return
    order_id, respondent_id = ids
    order = await repository.get(order_id)
    if order is None or callback.from_user.id != order.author_id:
        await callback.answer("Выбрать исполнителя может только автор", show_alert=True)
        return
    selection = await repository.select_response(order_id, order.author_id, respondent_id)
    if selection is None:
        await callback.answer("Исполнитель уже выбран или отклик не найден", show_alert=True)
        return

    await callback.answer("Исполнитель выбран", show_alert=True)
    if callback.message:
        await callback.message.answer(
            f"Для заявки #{order_id:03d} выбран исполнитель: "
            f'<a href="tg://user?id={selection.selected.respondent_id}">'
            f"{escape(selection.selected.respondent_name)}</a>."
        )

    for response in selection.responses:
        if response.respondent_id == selection.selected.respondent_id:
            text = (
                f'🎉 <a href="tg://user?id={selection.order.author_id}">'
                f"{escape(selection.order.author_name)}</a> выбрал вас исполнителем "
                f"заявки #{order_id:03d}. "
                "Свяжитесь с ним лично."
            )
        else:
            text = (
                f"По заявке #{order_id:03d} заказчик выбрал другого исполнителя. Спасибо за отклик!"
            )
        try:
            await bot.send_message(response.respondent_id, text)
        except TelegramAPIError as error:
            logger.warning(
                "Не удалось уведомить пользователя %s о выборе по заявке %s: %s",
                response.respondent_id,
                order_id,
                error,
            )

    if selection.order.published_chat_id and selection.order.published_message_id:
        try:
            await bot.edit_message_text(
                format_order(selection.order),
                chat_id=selection.order.published_chat_id,
                message_id=selection.order.published_message_id,
                reply_markup=assigned_order_keyboard(order_id),
            )
        except TelegramAPIError as error:
            logger.warning("Не удалось обновить опубликованную заявку %s: %s", order_id, error)


@router.callback_query(F.data.startswith("order:close:"))
async def close_order(callback: CallbackQuery, repository: OrderRepository) -> None:
    order_id = _callback_order_id(callback.data)
    if order_id is None:
        await callback.answer("Некорректный номер заявки", show_alert=True)
        return
    order = await repository.get(order_id)
    if order is None:
        await callback.answer("Заявка не найдена", show_alert=True)
        return
    if callback.from_user.id != order.author_id:
        await callback.answer("Закрыть заявку может только автор", show_alert=True)
        return
    if not await repository.close(order_id, callback.from_user.id):
        await callback.answer("Заявка уже закрыта", show_alert=True)
        return
    closed_order = await repository.get(order_id)
    await callback.answer("Заявка закрыта")
    if callback.message and closed_order:
        await callback.message.edit_text(format_order(closed_order), reply_markup=None)


def _draft_from_data(message: Message, data: dict[str, object]) -> OrderDraft:
    assert message.from_user is not None
    return OrderDraft(
        author_id=message.from_user.id,
        author_name=message.from_user.full_name,
        **data,
    )


def _draft_from_callback(callback: CallbackQuery, data: dict[str, object]) -> OrderDraft:
    return OrderDraft(
        author_id=callback.from_user.id,
        author_name=callback.from_user.full_name,
        **data,
    )


async def _publish_order(bot: Bot, settings: Settings, order: Order) -> Message:
    destination = {
        "chat_id": settings.target_chat_id,
        "message_thread_id": settings.orders_topic_id,
    }
    attachment_message: Message | None = None
    try:
        if order.attachment_type == "document" and order.attachment_file_id:
            attachment_message = await bot.send_document(
                document=order.attachment_file_id,
                caption=f"Вложение к заявке #{order.id:03d}",
                **destination,
            )
        elif order.attachment_type == "photo" and order.attachment_file_id:
            attachment_message = await bot.send_photo(
                photo=order.attachment_file_id,
                caption=f"Вложение к заявке #{order.id:03d}",
                **destination,
            )
        return await bot.send_message(
            text=format_order(order), reply_markup=order_keyboard(order.id), **destination
        )
    except TelegramAPIError:
        if attachment_message:
            try:
                await bot.delete_message(
                    chat_id=attachment_message.chat.id,
                    message_id=attachment_message.message_id,
                )
            except TelegramAPIError:
                logger.warning("Не удалось удалить вложение заявки %s", order.id)
        raise


def _callback_order_id(data: str | None) -> int | None:
    try:
        value = int((data or "").rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return None
    return value if value > 0 else None


def _callback_user_id(data: str | None) -> int | None:
    try:
        value = int((data or "").rsplit(":", 1)[1])
    except (IndexError, ValueError):
        return None
    return value if value > 0 else None


def _callback_selection_ids(data: str | None) -> tuple[int, int] | None:
    try:
        prefix, action, order_value, respondent_value = (data or "").split(":")
        order_id = int(order_value)
        respondent_id = int(respondent_value)
    except (ValueError, TypeError):
        return None
    if prefix != "order" or action != "select" or order_id < 1 or respondent_id < 1:
        return None
    return order_id, respondent_id
