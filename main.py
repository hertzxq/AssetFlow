import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import BaseFilter, Command
from config import BOT_TOKEN, ADMIN_ID
from database import (
    init_db, get_categories, get_products_by_category, get_product,
    add_to_cart, get_cart_items, clear_cart, create_order,
    get_pending_orders, get_order_items, add_category, add_product,
    delete_category, delete_product
)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Каталог 📋", callback_data="catalog")],
    [InlineKeyboardButton(text="Корзина 🛒", callback_data="cart")],
    [InlineKeyboardButton(text="Поддержка ❓", callback_data="support")],
])

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

class AddCategoryStates(StatesGroup):
    name = State()
    gender = State()

class AdminFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id == ADMIN_ID

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer("Привет! 👋 Я твой личный дворецкий! 🤖", reply_markup=main_menu)

@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мужская 👔", callback_data="gender_catalog_Мужская")],
        [InlineKeyboardButton(text="Женская 👗", callback_data="gender_catalog_Женская")],
        [InlineKeyboardButton(text="Детская 🧒", callback_data="gender_catalog_Детская")],
    ])
    await callback.message.answer("Выберите раздел каталога:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("gender_catalog_"))
async def show_gender_categories(callback: types.CallbackQuery):
    gender = callback.data.split("_")[-1]
    categories = await get_categories(gender=gender)
    if not categories:
        await callback.message.answer("Нет категорий в этом разделе.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"category_{cat[0]}")] for cat in categories
    ])
    await callback.message.answer("Выберите категорию:", reply_markup=keyboard)
    await callback.answer()

@dp.message(AddCategoryStates.name)
async def process_category_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мужская", callback_data="gender_Мужская")],
        [InlineKeyboardButton(text="Женская", callback_data="gender_Женская")],
        [InlineKeyboardButton(text="Детская", callback_data="gender_Детская")],
    ])
    await state.set_state(AddCategoryStates.gender)
    await message.answer("Выберите тип категории:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("gender_"))
async def process_category_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    data = await state.get_data()
    await add_category(data["name"], gender)
    await callback.message.answer(f"Категория '{data['name']}' ({gender}) добавлена. ✅")
    await state.clear()
    await callback.answer()

@dp.message(AdminFilter(), Command("add_category"))
async def start_add_category(message: types.Message, state: FSMContext):
    await state.set_state(AddCategoryStates.name)
    await message.answer("Введите название категории: 📂")

@dp.callback_query(F.data.startswith("category_"))
async def show_products(callback: types.CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    products = await get_products_by_category(category_id)
    if not products:
        await callback.message.answer("В этой категории нет товаров. 😔")
        return
    product_ids = [p[0] for p in products]
    await state.update_data(category_id=category_id, product_ids=product_ids, current_index=0)
    await show_product(callback.message, state)
    await callback.answer()

async def show_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_ids = data['product_ids']
    current_index = data['current_index']
    product_id = product_ids[current_index]
    product = await get_product(product_id)
    text = f"<b>{product[2]}</b> 🛍️\n{product[3]}\nЦена: {product[4]} руб. 💸"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить в корзину 🛒", callback_data=f"add_to_cart_{product_id}")],
        [InlineKeyboardButton(text="Назад ⬅️", callback_data="previous"), InlineKeyboardButton(text="Вперед ➡️", callback_data="next")],
        [InlineKeyboardButton(text="К категориям 📋", callback_data="catalog")]
    ])
    await message.answer_photo(photo=product[5], caption=text, reply_markup=keyboard)

@dp.callback_query(F.data == "next")
async def next_product(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']
    product_ids = data['product_ids']
    if current_index < len(product_ids) - 1:
        await state.update_data(current_index=current_index + 1)
        await show_product(callback.message, state)
    else:
        await callback.answer("Больше товаров нет. 🛑")
    await callback.answer()

@dp.callback_query(F.data == "previous")
async def prev_product(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']
    if current_index > 0:
        await state.update_data(current_index=current_index - 1)
        await show_product(callback.message, state)
    else:
        await callback.answer("Это первый товар. ⏮️")
    await callback.answer()

@dp.callback_query(F.data.startswith("add_to_cart_"))
async def add_to_cart_handler(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    await add_to_cart(user_id, product_id)
    await callback.answer("Товар добавлен в корзину! ✅")

@dp.callback_query(F.data == "cart")
async def show_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cart_items = await get_cart_items(user_id)
    if not cart_items:
        await callback.message.answer("Ваша корзина пуста. 🛒")
        return
    text = "Ваша корзина: 🛍️\n"
    total = 0
    for item in cart_items:
        product = await get_product(item['product_id'])
        text += f"{product[2]} x {item['quantity']} - {product[4] * item['quantity']} руб. 💸\n"
        total += product[4] * item['quantity']
    text += f"Итого: {total} руб. 💰"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оформить заказ 📦", callback_data="checkout")],
        [InlineKeyboardButton(text="Очистить корзину 🗑️", callback_data="clear_cart")]
    ])
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await clear_cart(user_id)
    await callback.message.answer("Корзина очищена. 🧹")
    await callback.answer()

@dp.callback_query(F.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart_items = await get_cart_items(user_id)
    if not cart_items:
        await callback.message.answer("Ваша корзина пуста. 🛒")
        return
    await state.set_state(OrderStates.name)
    await callback.message.answer("Введите ваше имя: ✍️")
    await callback.answer()

@dp.message(OrderStates.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(OrderStates.phone)
    await message.answer("Введите ваш номер телефона: 📞")

@dp.message(OrderStates.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(OrderStates.city)
    await message.answer("Введите ваш город: 🏙️")

@dp.message(OrderStates.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(OrderStates.delivery_method)
    await message.answer("Выберите способ доставки: Лично или онлайн (доставка, СДЭК, Авито доставка): 🚚")

@dp.message(OrderStates.delivery_method)
async def process_delivery(message: types.Message, state: FSMContext):
    await state.update_data(delivery_method=message.text)
    await state.set_state(OrderStates.payment_method)
    await message.answer("Выберите способ оплаты: 💳")

@dp.message(OrderStates.payment_method)
async def process_payment_method(message: types.Message, state: FSMContext):
    await state.update_data(payment_method=message.text)
    data = await state.get_data()
    user_id = message.from_user.id
    order_id = await create_order(user_id, data)
    items = await get_order_items(order_id)
    order_summary = ""
    total = 0
    for item in items:
        product = await get_product(item['product_id'])
        subtotal = item['price_at_purchase'] * item['quantity']
        total += subtotal
        order_summary += f"{product[2]} x {item['quantity']} — {subtotal} руб. 💸\n"
    admin_text = (
        f"<b>📦 Новый заказ #{order_id}</b>\n\n"
        f"<b>👤 Имя:</b> {data['name']}\n"
        f"<b>📞 Телефон:</b> {data['phone']}\n"
        f"<b>🏙 Город:</b> {data['city']}\n"
        f"<b>🚚 Доставка:</b> {data['delivery_method']}\n"
        f"<b>💳 Оплата:</b> {data['payment_method']}\n\n"
        f"<b>🛒 Товары:</b>\n{order_summary}\n"
        f"<b>Итого:</b> {total} руб. 💰"
    )
    await bot.send_message(ADMIN_ID, admin_text)
    await message.answer(f"✅ Ваш заказ #{order_id} успешно оформлен! 🎉\nМы свяжемся с вами в ближайшее время. 📞")
    await state.clear()

@dp.callback_query(F.data == "support")
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_for_question)
    await callback.message.answer("Напишите ваш вопрос: ❓")
    await callback.answer()

@dp.message(SupportStates.waiting_for_question)
async def forward_to_admin(message: types.Message, state: FSMContext):
    await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    await message.answer("Ваш вопрос отправлен менеджеру. ✅")
    await state.clear()

@dp.message(AdminFilter(), Command("add_product"))
async def start_add_product(message: types.Message, state: FSMContext):
    categories = await get_categories()
    if not categories:
        await message.answer("Сначала добавьте категории с помощью /add_category. ⚠️")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"add_product_cat_{cat[0]}")] for cat in categories
    ])
    await message.answer("Выберите категорию: 📋", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("add_product_cat_"))
async def select_category(callback: types.CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[3])
    await state.update_data(category_id=category_id)
    await state.set_state(AddProductStates.name)
    await callback.message.answer("Введите название товара: ✍️")
    await callback.answer()

@dp.message(AddProductStates.name)
async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.description)
    await message.answer("Введите описание товара: 📝")

@dp.message(AddProductStates.description)
async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddProductStates.price)
    await message.answer("Введите цену товара (в рублях): 💰")

@dp.message(AddProductStates.price)
async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(AddProductStates.photo)
        await message.answer("Отправьте фото товара: 📸")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную цену (число). ⚠️")

@dp.message(AddProductStates.photo, F.photo)
async def process_product_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    data = await state.get_data()
    await add_product(data['category_id'], data['name'], data['description'], data['price'], file_id)
    await message.answer("Товар успешно добавлен! 🎉")
    await state.clear()

@dp.message(AdminFilter(), Command("delete_category"))
async def start_delete_category(message: types.Message):
    categories = await get_categories()
    if not categories:
        await message.answer("Категорий нет для удаления. 📭")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"delete_category_{cat[0]}")] for cat in categories
    ])
    await message.answer("Выберите категорию для удаления: ❌", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("delete_category_"))
async def confirm_delete_category(callback: types.CallbackQuery):
    category_id = int(callback.data.split("_")[2])
    await delete_category(category_id)
    await callback.message.answer("Категория и все её товары удалены. ✅")
    await callback.answer()

@dp.message(AdminFilter(), Command("delete_product"))
async def start_delete_product(message: types.Message):
    categories = await get_categories()
    if not categories:
        await message.answer("Нет категорий. Добавьте их сначала. ⚠️")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"select_delete_prod_cat_{cat[0]}")] for cat in categories
    ])
    await message.answer("Выберите категорию товара: 🗂️", reply_markup=keyboard)


@dp.message(AdminFilter(), Command("add_category"))
async def start_add_category(message: types.Message, state: FSMContext):
    await state.set_state(AddCategoryStates.name)
    await message.answer("Введите название категории: 📂")

@dp.message(AddCategoryStates.name)
async def process_category_name(message: types.Message, state: FSMContext):
    await add_category(message.text)
    await message.answer(f"Категория '{message.text}' добавлена. ✅")
    await state.clear()


@dp.callback_query(F.data.startswith("select_delete_prod_cat_"))
async def show_products_for_deletion(callback: types.CallbackQuery):
    category_id = int(callback.data.split("_")[-1])
    products = await get_products_by_category(category_id)
    if not products:
        await callback.message.answer("В этой категории нет товаров. 📭")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p[2], callback_data=f"delete_product_{p[0]}")] for p in products
    ])
    await callback.message.answer("Выберите товар для удаления: ❌", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_product_"))
async def confirm_delete_product(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    await delete_product(product_id)
    await callback.message.answer("Товар удалён. ✅")
    await callback.answer()

async def main():
    await init_db()

    admin_commands = [
        BotCommand(command="/start", description="Запустить бота 🚀"),
        BotCommand(command="/add_category", description="Добавить категорию 📂"),
        BotCommand(command="/delete_category", description="Удалить категорию ❌"),
        BotCommand(command="/add_product", description="Добавить товар 🛍️"),
        BotCommand(command="/delete_product", description="Удалить товар ❌"),
    ]
    await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))

    user_commands = [
        BotCommand(command="/start", description="Запустить бота 🚀"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
