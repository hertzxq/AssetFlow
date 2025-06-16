from aiogram.fsm.state import State, StatesGroup

class CatalogStates(StatesGroup):
    browsing_category = State()

class OrderStates(StatesGroup):
    payment_method = State()

class SupportStates(StatesGroup):
    waiting_for_question = State()

class AddProductStates(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    photo = State()
    asset_file = State()

class AddCategoryStates(StatesGroup):
    name = State()
    section = State()

class AddBalanceStates(StatesGroup):
    user_id = State()
    balance_amount = State()

class UserAddBalanceStates(StatesGroup):
    amount = State()
    payment_method = State()
    yookassa_payment = State()