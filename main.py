import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeAllPrivateChats, BotCommand

from config import BOT_TOKEN
from database import init_db
from middleware import TimeMiddleware
from states import CatalogStates, AddProductStates, SupportStates, OrderStates, AddCategoryStates, AddBalanceStates

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())  # Явно указываем хранилище состояний

dp.update.middleware(TimeMiddleware())

async def main():
    await init_db()

    from handlers import cmd_start, show_catalog, show_section_categories, process_category_name
    from handlers import process_category_section, start_add_category, show_products, show_product
    from handlers import next_product, prev_product, add_to_cart_handler, send_asset_url, show_cart
    from handlers import clear_cart_handler, start_checkout, start_support
    from handlers import forward_to_admin, start_add_product, select_category, process_product_name
    from handlers import process_product_description, process_product_price, process_product_photo
    from handlers import process_asset_file, invalid_asset_file, start_delete_category, confirm_delete_category
    from handlers import start_delete_product, show_products_for_deletion, confirm_delete_product
    from handlers import show_balance, start_add_balance, process_user_id, process_balance_amount, AdminFilter

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
    dp.callback_query.register(start_support, F.data == "support")
    dp.message.register(forward_to_admin, SupportStates.waiting_for_question)
    dp.message.register(start_add_product, AdminFilter(), Command("add_product"))
    dp.callback_query.register(select_category, F.data.startswith("add_product_cat_"))
    dp.message.register(process_product_name, AddProductStates.name)
    dp.message.register(process_product_description, AddProductStates.description)
    dp.message.register(process_product_price, AddProductStates.price)
    dp.message.register(process_product_photo, AddProductStates.photo, F.photo)
    dp.message.register(process_asset_file, AddProductStates.asset_file, F.document)
    dp.message.register(invalid_asset_file, AddProductStates.asset_file)
    dp.message.register(start_delete_category, AdminFilter(), Command("delete_category"))
    dp.callback_query.register(confirm_delete_category, F.data.startswith("delete_category_"))
    dp.message.register(start_delete_product, AdminFilter(), Command("delete_product"))
    dp.callback_query.register(show_products_for_deletion, F.data.startswith("select_delete_prod_cat_"))
    dp.callback_query.register(confirm_delete_product, F.data.startswith("delete_product_"))
    dp.callback_query.register(show_balance, F.data == "balance")
    dp.message.register(start_add_balance, AdminFilter(), Command("add_balance"))
    dp.message.register(process_user_id, AddBalanceStates.user_id)
    dp.message.register(process_balance_amount, AddBalanceStates.balance_amount)

    admin_commands = [
        BotCommand(command="/start", description="Запустить бота 🚀"),
        BotCommand(command="/add_category", description="Добавить категорию 📂"),
        BotCommand(command="/delete_category", description="Удалить категорию ❌"),
        BotCommand(command="/add_product", description="Добавить ассет 📦"),
        BotCommand(command="/delete_product", description="Удалить ассет ❌"),
        BotCommand(command="/add_balance", description="Пополнить баланс 💰"),
    ]
    await bot.set_my_commands(admin_commands, scope=BotCommandScopeAllPrivateChats())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())