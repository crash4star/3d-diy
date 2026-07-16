from diy_bot.models import OrderDraft
from diy_bot.presentation import (
    CANCEL_BUTTON,
    CREATE_ORDER_BUTTON,
    MY_ORDERS_BUTTON,
    RULES_BUTTON,
    format_order,
    main_menu_keyboard,
)


def test_order_text_is_html_escaped() -> None:
    draft = OrderDraft(
        author_id=1,
        author_name="Автор",
        description="<script>alert(1)</script>",
        quantity="1",
        dimensions="10 × 10",
        model_info="нет",
        material="PLA",
        color="чёрный",
        deadline="завтра",
        budget="обмен",
        building="1",
    )

    text = format_order(draft, preview=True)

    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_main_menu_contains_primary_actions() -> None:
    keyboard = main_menu_keyboard()
    button_texts = {button.text for row in keyboard.keyboard for button in row}

    assert button_texts == {
        CREATE_ORDER_BUTTON,
        MY_ORDERS_BUTTON,
        RULES_BUTTON,
        CANCEL_BUTTON,
    }
    assert keyboard.is_persistent is True
