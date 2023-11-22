import logging, os, django
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Text
from asgiref.sync import sync_to_async
from bs4 import BeautifulSoup
from config import token
# Импортируйте ваши модели Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'burotime_kg.settings')
django.setup()
from apps.products.models import Category, Product, Favorite

API_TOKEN = token
# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN,parse_mode='Html')
dp = Dispatcher(bot)

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
def get_favorites_for_user(user_id):
    favorites = Favorite.objects.filter(user_id=user_id).select_related('product')
    return [(favorite.product.id, favorite.product.name) for favorite in favorites]

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
    await message.reply("Привет! Я бот бренда Burotime\n/categories - показать категории продукций\n/favorite - показать все избранные продукты")

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
    
    keyboard = types.InlineKeyboardMarkup()
    for i in range(0, len(product_buttons), 3):
        keyboard.row(*product_buttons[i:i+3])

    if pagination_buttons:
        keyboard.row(*pagination_buttons)
    back_button = types.InlineKeyboardButton(text="Назад к категориям", callback_data="back_to_categories")
    keyboard.add(back_button)
    
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
    # back_button = types.InlineKeyboardButton(text="Назад к продуктам", callback_data=f"back_to_products:{product.category_id}")
    # keyboard.add(back_button)
    product_description = BeautifulSoup(product.description.html, 'html.parser').get_text()
    caption = f"{product.name}\n{product_description}"
    with open(product.image.path, 'rb') as photo:
        await bot.send_photo(callback_query.from_user.id, photo=photo, caption=caption,reply_markup=keyboard)
    # await bot.send_photo(callback_query.from_user.id, photo=product.image.url)
    # await bot.send_message(callback_query.from_user.id, f"{product.name}\n{product.description}", reply_markup=keyboard)

@dp.callback_query_handler(lambda c: c.data == 'back_to_categories')
async def back_to_categories(callback_query: types.CallbackQuery):
    await show_categories(callback_query.message)
@dp.callback_query_handler(lambda c: c.data.startswith('back_to_products'))
async def back_to_products(callback_query: types.CallbackQuery):
    _, category_id = callback_query.data.split(':')
    category_id = int(category_id)
    await handle_category(callback_query.message, category_id, 1)  # Предполагается, что 1 - это страница


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



@dp.message_handler(commands=['favorite'])
async def list_favorites(message: types.Message):
    user_id = message.from_user.id
    favorites = await get_favorites_for_user(user_id)
    if not favorites:
        await message.answer("У вас пока нет избранных продуктов.")
        return
    
    text = "Ваши избранные продукты:\n\n"
    text += "\n".join([f"{i+1}. {name}" for i, (product_id, name) in enumerate(favorites)])
    await message.answer(text)


if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)
