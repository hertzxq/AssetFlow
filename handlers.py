from aiogram import types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from main import bot
from states import CatalogStates, OrderStates, SupportStates, AddProductStates, AddCategoryStates, AddBalanceStates, \
    UserAddBalanceStates
from database import get_categories, get_products_by_category, get_product, add_to_cart, get_cart_items, clear_cart, \
    create_order, get_order_items, add_category, add_product, delete_category, delete_product, get_user_balance, \
    update_user_balance
from config import ADMIN_ID
import aiosqlite
import logging
import asyncio
import requests

logging.basicConfig(level=logging.INFO)

# Главное меню
main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Каталог 📋", callback_data="catalog")],
    [InlineKeyboardButton(text="Корзина 🛒", callback_data="cart")],
    [InlineKeyboardButton(text="Баланс 💰", callback_data="balance")],
    [InlineKeyboardButton(text="Поддержка ❓", callback_data="support")],
])


# Фильтр для администратора
class AdminFilter:
    async def __call__(self, message: types.Message) -> bool:
        return message.from_user.id == ADMIN_ID


# Обработчик команды /start
async def cmd_start(message: types.Message):
    await message.answer("Привет! 👋 Я твой бот для поиска моделей/ассетов и всего разного из мира 3д! 🤖",
                         reply_markup=main_menu)


# Показать каталог
async def show_catalog(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Бесплатные Assets 🆓", callback_data="section_catalog_free"),
            InlineKeyboardButton(text="Платные Assets 💰", callback_data="section_catalog_paid")
        ],
        [InlineKeyboardButton(text="Корзина 🛒", callback_data="cart")],
        [InlineKeyboardButton(text="Баланс 💰", callback_data="balance")],
        [InlineKeyboardButton(text="Поддержка ❓", callback_data="support")]
    ])
    if callback.message.text:
        await callback.message.edit_text("Выберите раздел каталога:", reply_markup=keyboard)
    else:
        await callback.message.answer("Выберите раздел каталога:", reply_markup=keyboard)
    await callback.answer()


# Показать баланс
async def show_balance(callback: types.CallbackQuery):
    balance = await get_user_balance(callback.from_user.id)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="top_up_balance")],
        [InlineKeyboardButton(text="⬅️ Вернуться", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text(f"💸 Выберите способ пополнения\n20:53\n\n💰 Ваш баланс: {balance:.2f} руб.",
                                     reply_markup=keyboard)
    await callback.answer()


# Начало процесса пополнения баланса
async def start_top_up_balance(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Ручной ввод", callback_data="manual_top_up")],
        [InlineKeyboardButton(text="💸 СБП (Юкасса)", callback_data="yookassa_sbp")],
        [InlineKeyboardButton(text="⬅️ Вернуться", callback_data="back_to_menu")]
    ])
    await callback.message.edit_text("Выберите способ пополнения:", reply_markup=keyboard)
    await callback.answer()


# Обработка ручного ввода суммы
async def start_manual_top_up(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserAddBalanceStates.amount)
    await callback.message.answer("Введите сумму для пополнения: 💰")
    await callback.answer()


# Обработка выбора оплаты через Юкассу и СБП
async def start_yookassa_sbp(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(UserAddBalanceStates.amount)
    await callback.message.answer("Введите сумму для пополнения через СБП (Юкасса): 💸")
    await state.update_data(payment_method="yookassa_sbp")
    await callback.answer()


# Обработка суммы пополнения
async def process_top_up_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Сумма должна быть положительной. ⚠️")
            return
        data = await state.get_data()
        payment_method = data.get("payment_method", "manual")
        user_id = message.from_user.id

        if payment_method == "yookassa_sbp":
            await state.update_data(amount=amount)
            await state.set_state(UserAddBalanceStates.yookassa_payment)
            payment_url = await create_yookassa_payment(user_id, amount)
            if payment_url:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Оплатить через СБП", url=payment_url)],
                    [InlineKeyboardButton(text="⬅️ Вернуться", callback_data="back_to_menu")]
                ])
                await message.answer(f"Перейдите по ссылке для оплаты {amount:.2f} руб. через СБП:\n{payment_url}",
                                     reply_markup=keyboard)
            else:
                await message.answer("Ошибка при создании платежа. Попробуйте снова. ⚠️")
                await state.clear()
        else:
            success = await update_user_balance(user_id, amount)
            if success:
                new_balance = await get_user_balance(user_id)
                await message.answer(
                    f"Баланс успешно пополнен на {amount:.2f} руб. ✅\nНовый баланс: {new_balance:.2f} руб. 💰")
            else:
                await message.answer("Ошибка при пополнении баланса. ⚠️")
            await state.clear()
    except ValueError:
        await message.answer("Введите корректное число. ⚠️")


# Создание платежа через Юкассу
async def create_yookassa_payment(user_id, amount):
    shop_id = "your_shop_id"  # Замените на ваш Shop ID от Юкассы
    secret_key = "your_secret_key"  # Замените на ваш секретный ключ
    url = "https://api.yookassa.ru/v3/payments"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {secret_key}"
    }
    payload = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "capture": True,
        "description": f"Пополнение баланса для пользователя {user_id}",
        "payment_method_data": {"type": "sbp"},
        "confirmation": {
            "type": "redirect",
            "return_url": "https://your-bot-domain.com/return"  # Замените на ваш URL
        },
        "metadata": {"user_id": user_id}
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json().get("confirmation", {}).get("confirmation_url")
    return None


# Обработка возврата после оплаты через Юкассу
async def handle_yookassa_return(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    user_id = callback.from_user.id
    success = True  # Замените на реальную проверку статуса платежа
    if success:
        await update_user_balance(user_id, amount)
        new_balance = await get_user_balance(user_id)
        await callback.message.answer(
            f"Баланс успешно пополнен на {amount:.2f} руб. ✅\nНовый баланс: {new_balance:.2f} руб. 💰")
    else:
        await callback.message.answer("Ошибка при обработке оплаты. Попробуйте снова. ⚠️")
    await state.clear()
    await callback.answer()


# Начало процесса пополнения баланса администратором
async def start_add_balance(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(AddBalanceStates.user_id)
    await message.answer("Введите ID пользователя для пополнения баланса: 🆔")


# Обработка ID пользователя
async def process_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(user_id=user_id)
        await state.set_state(AddBalanceStates.balance_amount)
        await message.answer("Введите сумму для пополнения: 💰")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID пользователя. ⚠️")


# Обработка суммы пополнения администратором
async def process_balance_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("Сумма должна быть положительной. ⚠️")
            return
        data = await state.get_data()
        user_id = data['user_id']
        success = await update_user_balance(user_id, amount)
        if success:
            await message.answer(f"Баланс пользователя {user_id} пополнен на {amount:.2f} руб. ✅")
            await bot.send_message(user_id,
                                   f"Ваш баланс пополнен на {amount:.2f} руб. 💰 Новый баланс: {await get_user_balance(user_id):.2f} руб.")
        else:
            await message.answer("Ошибка при пополнении баланса. ⚠️")
        await state.clear()
    except ValueError:
        await message.answer("Введите корректное число. ⚠️")


# Показать категории раздела
async def show_section_categories(callback: types.CallbackQuery, state: FSMContext):
    section = callback.data.split("_")[-1]
    categories = await get_categories(section=section)
    if not categories:
        await callback.message.answer("Нет категорий в этом разделе.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"category_{cat[0]}")] for cat in categories
    ])
    await callback.message.answer("Выберите категорию:", reply_markup=keyboard)
    await callback.answer()


async def process_category_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Бесплатно", callback_data="section_free")],
        [InlineKeyboardButton(text="Платно", callback_data="section_paid")],
    ])
    await state.set_state(AddCategoryStates.section)
    await message.answer("Выберите тип категории:", reply_markup=keyboard)


async def process_category_section(callback: types.CallbackQuery, state: FSMContext):
    section = callback.data.split("_")[1]
    data = await state.get_data()
    await add_category(data["name"], section)
    await callback.message.answer(f"Категория '{data['name']}' ({section}) добавлена. ✅")
    await state.clear()
    await callback.answer()


async def start_add_category(message: types.Message, state: FSMContext):
    await state.set_state(AddCategoryStates.name)
    await message.answer("Введите название категории: 📂")


async def show_products(callback: types.CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    products = await get_products_by_category(category_id)
    if not products:
        await callback.message.answer("В этой категории нет ассетов. 😔")
        return
    product_ids = [p[0] for p in products]
    await state.update_data(category_id=category_id, product_ids=product_ids, current_index=0)
    await state.set_state(CatalogStates.browsing_category)
    await show_product(callback.message, state)
    await callback.answer()


async def show_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    product_ids = data['product_ids']
    current_index = data['current_index']
    product_id = product_ids[current_index]
    product = await get_product(product_id)
    if product[4] == 0:
        price_text = "Бесплатно 🎁"
    else:
        price_text = f"Цена: {product[4]:.2f} руб. 💸"
    text = f"<b>{product[2]}</b> 🛍️\n{product[3]}\n{price_text}"
    if product[4] == 0:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Получить актив 🌐", callback_data=f"get_asset_{product_id}")],
            [InlineKeyboardButton(text="Назад ⬅️", callback_data="previous"),
             InlineKeyboardButton(text="Вперед ➡️", callback_data="next")],
            [InlineKeyboardButton(text="К категориям 📋", callback_data="catalog")]
        ])
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Добавить в корзину 🛒", callback_data=f"add_to_cart_{product_id}")],
            [InlineKeyboardButton(text="Назад ⬅️", callback_data="previous"),
             InlineKeyboardButton(text="Вперед ➡️", callback_data="next")],
            [InlineKeyboardButton(text="К категориям 📋", callback_data="catalog")]
        ])
    await message.answer_photo(photo=product[5], caption=text, reply_markup=keyboard)


async def next_product(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']
    product_ids = data['product_ids']
    if current_index < len(product_ids) - 1:
        await state.update_data(current_index=current_index + 1)
        await show_product(callback.message, state)
    else:
        await callback.answer("Больше ассетов нет. 🛑")
    await callback.answer()


async def prev_product(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_index = data['current_index']
    if current_index > 0:
        await state.update_data(current_index=current_index - 1)
        await show_product(callback.message, state)
    else:
        await callback.answer("Это первый ассет. ⏮️")
    await callback.answer()


# Добавление продукта в корзину (ограничение до 1 копии)
async def add_to_cart_handler(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    cart_items = await get_cart_items(user_id)

    # Проверяем, есть ли уже этот ассет в корзине
    if any(item['product_id'] == product_id for item in cart_items):
        await callback.answer("Этот ассет уже в корзине! Вы можете добавить только 1 копию. ✅", show_alert=True)
    else:
        await add_to_cart(user_id, product_id, quantity=1)  # Устанавливаем количество 1
        await callback.answer("Ассет добавлен в корзину! ✅")
        await callback.message.edit_text("Ассет добавлен в корзину. Что дальше?", reply_markup=main_menu)


async def handle_random_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state and not message.text.startswith('/'):
        await message.answer("Не понимаю ваш запрос. Пожалуйста, используйте кнопки или команды. 🔄",
                             reply_markup=main_menu)


async def send_asset_url(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    product = await get_product(product_id)
    if product[4] == 0:
        await callback.message.answer_document(document=product[6], caption="Вот ваш бесплатный ассет 🌟")
    else:
        await callback.message.answer("Этот ассет платный. Пожалуйста, добавьте его в корзину. 🛒")
    await callback.answer()


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
        text += f"{product[2]} x {item['quantity']} - {product[4] * item['quantity']:.2f} руб. 💸\n"
        total += product[4] * item['quantity']
    text += f"Итого: {total:.2f} руб. 💰\nВаш баланс: {await get_user_balance(user_id):.2f} руб. 💳"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить 📦", callback_data="checkout")],
        [InlineKeyboardButton(text="Очистить корзину 🗑️", callback_data="clear_cart")]
    ])
    await callback.message.answer(text, reply_markup=keyboard)
    await callback.answer()


async def clear_cart_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await clear_cart(user_id)
    await callback.message.answer("Корзина очищена. 🧹")
    await callback.answer()


async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    logging.info("Starting checkout process for user %s", callback.from_user.id)
    user_id = callback.from_user.id
    cart_items = await get_cart_items(user_id)
    if not cart_items:
        await callback.message.answer("Ваша корзина пуста. 🛒")
        return
    logging.info("Cart items retrieved: %s", cart_items)

    products = await asyncio.gather(*(get_product(item['product_id']) for item in cart_items))
    total_price = sum(product[4] * item['quantity'] for product, item in zip(products, cart_items))
    balance = await get_user_balance(user_id)
    if balance < total_price:
        await callback.message.answer("Недостаточно средств на балансе. 💸 Пожалуйста, пополните баланс.")
        return

    order_id, error = await create_order(user_id, {'payment_method': 'По умолчанию'})
    if error:
        logging.error("Error creating order for user %s: %s", user_id, error)
        await callback.message.answer(error)
        return

    items = await get_order_items(order_id)
    order_summary = ""
    total = 0
    for item in items:
        product = await get_product(item['product_id'])
        subtotal = item['price_at_purchase'] * item['quantity']
        total += subtotal
        order_summary += f"{product[2]} x {item['quantity']} — {subtotal:.2f} руб. 💸\n"
    admin_text = (
        f"<b>📦 Новый заказ #{order_id}</b>\n\n"
        f"<b>💳 Оплата:</b> По умолчанию\n\n"
        f"<b>🛒 Ассеты:</b>\n{order_summary}\n"
        f"<b>Итого:</b> {total:.2f} руб. 💰"
    )
    await bot.send_message(ADMIN_ID, admin_text)

    await callback.message.answer(
        f"✅ Ваш заказ #{order_id} успешно оформлен! 🎉\nВаш баланс: {await get_user_balance(user_id):.2f} руб. 💳")
    for item in items:
        product = await get_product(item['product_id'])
        for _ in range(item['quantity']):
            await callback.message.answer_document(document=product[6], caption=f"Ваш ассет: {product[2]} 🌟")

    await clear_cart(user_id)


async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_for_question)
    await callback.message.answer("Напишите ваш вопрос: ❓")
    await callback.answer()


async def forward_to_admin(message: types.Message, state: FSMContext):
    await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    await message.answer("Ваш вопрос отправлен менеджеру. ✅")
    await state.clear()


async def start_add_product(message: types.Message, state: FSMContext):
    categories = await get_categories()
    if not categories:
        await message.answer("Сначала добавьте категории с помощью /add_category. ⚠️")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        category_id, category_name = cat
        async with aiosqlite.connect('bot.db') as db:
            async with db.execute('SELECT section FROM categories WHERE id=?', (category_id,)) as cursor:
                row = await cursor.fetchone()
                section = row[0] if row else "unknown"
        button_text = f"{category_name} ({section})"
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text=button_text, callback_data=f"add_product_cat_{category_id}")])
    await state.set_state(AddProductStates.category)
    await message.answer("Выберите категорию: 📋", reply_markup=keyboard)


async def select_category(callback: types.CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[3])
    await state.update_data(category_id=category_id)
    await state.set_state(AddProductStates.name)
    await callback.message.answer("Введите название ассета:", reply_markup=types.ReplyKeyboardRemove())
    await callback.answer()


async def process_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddProductStates.description)
    await message.answer("Введите описание ассета: 📝")


async def process_product_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    data = await state.get_data()
    category_id = data['category_id']

    async with aiosqlite.connect('bot.db') as db:
        async with db.execute('SELECT section FROM categories WHERE id=?', (category_id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] == 'free':
                await state.update_data(price=0.0, is_free=1)
                await state.set_state(AddProductStates.photo)
                await message.answer("Выберите фото ассета: 📸")
            else:
                await state.set_state(AddProductStates.price)
                await message.answer("Введите цену ассета: 💰")


async def process_product_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price < 0:
            await message.answer("Цена не может быть отрицательной. ⚠️")
            return
        await state.update_data(price=price)
        is_free = 1 if price == 0 else 0
        await state.update_data(is_free=is_free)
        await state.set_state(AddProductStates.photo)
        await message.answer("Выберите фото ассета: 📸")
    except ValueError:
        await message.answer("Введите корректное число. ⚠️")


async def process_product_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    await state.update_data(photo=file_id)
    await state.set_state(AddProductStates.asset_file)
    await message.answer("Загрузите файл ассета (.fbx, .jpg, .obj, .blend): 📤")


async def process_asset_file(message: types.Message, state: FSMContext):
    if message.document:
        file_name = message.document.file_name
        if file_name.lower().endswith(('.fbx', '.jpg', '.obj', '.blend')):
            file_id = message.document.file_id
            data = await state.get_data()
            await add_product(data['category_id'], data['name'],
                              data['description'], data['price'],
                              data['photo'], file_id,
                              data['is_free'])
            await message.answer("Ассет успешно добавлен! 😄🎉")
            await state.clear()
        else:
            await message.answer("Неверный формат файла. Загрузите файл в формате .fbx, .jpg, .obj или .blend.")
    else:
        await message.answer("Пожалуйста, загрузите файл в формате .fbx, .jpg, .obj или .blend.")


async def invalid_asset_file(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, загрузите файл в формате .fbx, .jpg, .obj или .blend.")


async def start_delete_category(message: types.Message):
    categories = await get_categories()
    if not categories:
        await message.answer("Категорий нет для удаления. 📭")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"delete_category_{cat[0]}")] for cat in categories
    ])
    await message.answer("Выберите категорию для удаления: ❌", reply_markup=keyboard)


async def confirm_delete_category(callback: types.CallbackQuery):
    category_id = int(callback.data.split("_")[2])
    await delete_category(category_id)
    await callback.message.answer("Категория и все её ассеты удалены. ✅")
    await callback.answer()


async def start_delete_product(message: types.Message):
    categories = await get_categories()
    if not categories:
        await message.answer("Нет категорий. Добавьте их сначала. ⚠️")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=cat[1], callback_data=f"select_delete_prod_cat_{cat[0]}")] for cat in categories
    ])
    await message.answer("Выберите категорию ассета: 🗂️", reply_markup=keyboard)


async def show_products_for_deletion(callback: types.CallbackQuery):
    category_id = int(callback.data.split("_")[-1])
    products = await get_products_by_category(category_id)
    if not products:
        await callback.message.answer("В этой категории нет ассетов. 📭")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=p[2], callback_data=f"delete_product_{p[0]}")] for p in products
    ])
    await callback.message.answer("Выберите ассет для удаления: ❌", reply_markup=keyboard)
    await callback.answer()


async def confirm_delete_product(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    await delete_product(product_id)
    await callback.message.answer("Ассет удалён. ✅")
    await callback.answer()