from aiogram.fsm.state import State, StatesGroup

class CatalogStates(StatesGroup):
    browsing_category = State()

class OrderStates(StatesGroup):
    name = State()
    phone = State()
    city = State()
    delivery_method = State()
    payment_method = State()

class SupportStates(StatesGroup):
    waiting_for_question = State()

class AddProductStates(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    photo = State()
    asset_url = State()

class AddCategoryStates(StatesGroup):
    name = State()
    section = State()