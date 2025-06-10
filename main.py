import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from config import BOT_TOKEN, ADMIN_ID
from database import init_db
from middleware import TimeMiddleware
from states import CatalogStates, AddProductStates, SupportStates, OrderStates, AddCategoryStates

# Создание бота и диспетчера
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Регистрация middleware
dp.update.middleware(TimeMiddleware())

async def main():
    await init_db()

    # Динамический импорт обработчиков после создания bot и dp
    from handlers import cmd_start, show_catalog, show_section_categories, process_category_name
    from handlers import process_category_section, start_add_category, show_products, show_product
    from handlers import next_product, prev_product, add_to_cart_handler, send_asset_url, show_cart
    from handlers import clear_cart_handler, start_checkout, process_name, process_phone
    from handlers import process_city, process_delivery, process_payment_method, start_support
    from handlers import forward_to_admin, start_add_product, select_category, process_product_name
    from handlers import process_product_description, process_product_price, process_product_photo
    from handlers import process_asset_url, start_delete_category, confirm_delete_category
    from handlers import start_delete_product, show_products_for_deletion, confirm_delete_product, AdminFilter

    # Регистрация обработчиков
    dp.message.register(cmd_start, Command("start"))
    dp.callback_query.register(show_catalog, F.data == "catalog")
    dp.callback_query.register(show_section_categories, F.data.startswith("section_catalog_"))
    dp.message.register(process_category_name, AddCategoryStates.name)
    dp.callback_query.register(process_category_section, F.data.startswith("section_"))
    dp.message.register(start_add_category, AdminFilter(), Command("add_category"))
    dp.callback_query.register(show_products, F.data.startswith("category_"))
    dp.message.register(show_product, StateFilter(CatalogStates.browsing_category))
    dp.callback_query.register(next_product, F.data == "next")
    dp.callback_query.register(prev_product, F.data == "previous")
    dp.callback_query.register(add_to_cart_handler, F.data.startswith("add_to_cart_"))
    dp.callback_query.register(send_asset_url, F.data.startswith("get_asset_"))
    dp.callback_query.register(show_cart, F.data == "cart")
    dp.callback_query.register(clear_cart_handler, F.data == "clear_cart")
    dp.callback_query.register(start_checkout, F.data == "checkout")
    dp.message.register(process_name, OrderStates.name)
    dp.message.register(process_phone, OrderStates.phone)
    dp.message.register(process_city, OrderStates.city)
    dp.message.register(process_delivery, OrderStates.delivery_method)
    dp.message.register(process_payment_method, OrderStates.payment_method)
    dp.callback_query.register(start_support, F.data == "support")
    dp.message.register(forward_to_admin, SupportStates.waiting_for_question)
    dp.message.register(start_add_product, AdminFilter(), Command("add_product"))
    dp.callback_query.register(select_category, F.data.startswith("add_product_cat_"))
    dp.message.register(process_product_name, AddProductStates.name)
    dp.message.register(process_product_description, AddProductStates.description)
    dp.message.register(process_product_price, AddProductStates.price)
    dp.message.register(process_product_photo, AddProductStates.photo, F.photo)
    dp.message.register(process_asset_url, AddProductStates.asset_url)
    dp.message.register(start_delete_category, AdminFilter(), Command("delete_category"))
    dp.callback_query.register(confirm_delete_category, F.data.startswith("delete_category_"))
    dp.message.register(start_delete_product, AdminFilter(), Command("delete_product"))
    dp.callback_query.register(show_products_for_deletion, F.data.startswith("select_delete_prod_cat_"))
    dp.callback_query.register(confirm_delete_product, F.data.startswith("delete_product_"))

    admin_commands = [
        BotCommand(command="/start", description="Запустить бота 🚀"),
        BotCommand(command="/add_category", description="Добавить категорию 📂"),
        BotCommand(command="/delete_category", description="Удалить категорию ❌"),
        BotCommand(command="/add_product", description="Добавить ассет 🛍️"),
        BotCommand(command="/delete_product", description="Удалить ассет ❌"),
    ]
    await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))

    user_commands = [
        BotCommand(command="/start", description="Запустить бота 🚀"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())