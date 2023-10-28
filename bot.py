import logging
import os
import django
from aiogram import Bot, Dispatcher, types
from asgiref.sync import sync_to_async

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token='6688411275:AAEVAkEGygPvRMgvTpg4uYkvMxE1iv5FX68')
dp = Dispatcher(bot)

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'burotime_kg.settings')
django.setup()

# Импорт моделей Django
from apps.products.models import Category, Product, Favorite

# Асинхронные функции для работы с моделями Django
@sync_to_async
def get_categories(page=1):
    start = (page - 1) * 6
    end = start + 6
    return list(Category.objects.all()[start:end]), Category.objects.count()

@sync_to_async
def get_paginated_products(category_id, page=1):
    category = Category.objects.get(id=category_id)
    products = Product.objects.filter(category=category)
    start = (page - 1) * 6
    end = start + 6
    return list(products[start:end]), products.count()

@sync_to_async
def get_product(product_id):
    return Product.objects.get(id=product_id)

@sync_to_async
def add_to_favorites(user_id, product_id):
    product = Product.objects.get(id=product_id)
    Favorite.objects.get_or_create(user_id=user_id, product=product)

@sync_to_async
def remove_from_favorites(user_id, product_id):
    product = Product.objects.get(id=product_id)
    Favorite.objects.filter(user_id=user_id, product=product).delete()

@sync_to_async
def is_favorite(user_id, product_id):
    product = Product.objects.get(id=product_id)
    return Favorite.objects.filter(user_id=user_id, product=product).exists()

# Команда старт
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply("Привет! Я бот-каталог магазина. Чем я могу вам помочь?")

# Команда помощь
@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    await message.reply("Команды бота:\n/start - начать общение\n/help - помощь\n/categories - показать категории товаров")

# Команда категории
@dp.message_handler(commands=['categories'])
async def show_categories(message: types.Message):
    categories, total = await get_categories()
    text = "Выберите категорию:\n\n"
    text += "\n".join([f"{i+1}. {category.title}" for i, category in enumerate(categories)])
    buttons = [types.InlineKeyboardButton(text=str(i+1), callback_data=f"category:{category.id}:1") for i, category in enumerate(categories)]
    if total > 6:
        buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"categories:2"))
    keyboard = types.InlineKeyboardMarkup(row_width=5)
    keyboard.add(*buttons)
    await message.reply(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('categories:'))
async def paginate_categories(callback_query: types.CallbackQuery):
    _, page = callback_query.data.split(':')
    page = int(page)
    categories, total = await get_categories(page)
    text = "Выберите категорию:\n\n"
    text += "\n".join([f"{i}. {category.title}" for i, category in enumerate(categories)])
    buttons = [types.InlineKeyboardButton(text=str(i), callback_data=f"category:{category.id}:1") for i, category in enumerate(categories)]
    if page > 1:
        buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"categories:{page-1}"))
    if total > page * 6:
        buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"categories:{page+1}"))
    keyboard = types.InlineKeyboardMarkup(row_width=5)
    keyboard.add(*buttons)
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('category:'))
async def handle_category(callback_query: types.CallbackQuery):
    _, category_id, page = callback_query.data.split(':')
    page = int(page)
    products, total = await get_paginated_products(category_id, page)
    
    text = "Продукты:\n\n" + "\n".join([f"{i}. {product.name}" for i, product in enumerate(products, start=1)])
    
    product_buttons = [types.InlineKeyboardButton(text=str(i), callback_data=f"product:{product.id}") for i, product in enumerate(products, start=1)]
    pagination_buttons = []
    if page > 1:
        pagination_buttons.append(types.InlineKeyboardButton(text="⬅️", callback_data=f"category:{category_id}:{page-1}"))
    if total > page * 6:
        pagination_buttons.append(types.InlineKeyboardButton(text="➡️", callback_data=f"category:{category_id}:{page+1}"))
    
    keyboard = types.InlineKeyboardMarkup(row_width=5)
    keyboard.row(*product_buttons)
    if pagination_buttons:
        keyboard.row(*pagination_buttons)
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('product:'))
async def handle_product(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split(':')[-1])
    product = await get_product(product_id)
    is_in_favorites = await is_favorite(callback_query.from_user.id, product_id)
    
    if is_in_favorites:
        buttons = [types.InlineKeyboardButton(text="Удалить из избранного", callback_data=f"favorite:remove:{product.id}")]
    else:
        buttons = [types.InlineKeyboardButton(text="Добавить в избранное", callback_data=f"favorite:add:{product.id}")]
    
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(*buttons)
    await bot.send_message(callback_query.from_user.id, f"{product.name}\nЦена: {product.price}\n{product.description}", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('favorite:add:'))
async def add_to_favorite(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split(':')[-1])
    await add_to_favorites(callback_query.from_user.id, product_id)
    product = await get_product(product_id)
    await bot.send_message(callback_query.from_user.id, f"{product.name} добавлен в избранное")

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('favorite:remove:'))
async def remove_from_favorite(callback_query: types.CallbackQuery):
    product_id = int(callback_query.data.split(':')[-1])
    await remove_from_favorites(callback_query.from_user.id, product_id)
    product = await get_product(product_id)
    await bot.send_message(callback_query.from_user.id, f"{product.name} удален из избранного")

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
