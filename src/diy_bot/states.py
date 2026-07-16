from aiogram.fsm.state import State, StatesGroup


class OrderForm(StatesGroup):
    description = State()
    quantity = State()
    dimensions = State()
    model = State()
    material = State()
    color = State()
    deadline = State()
    budget = State()
    preview = State()
