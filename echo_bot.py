import pprint

from environs import Env
import logging
import redis
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from strapi_fetcher import fetch_products, get_product_by_id, \
    create_or_update_cart, get_cart_by_id, delete_cart_product

_database = None


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def start(update, context):
    products = fetch_products()['data']
    keyboard = [
        [InlineKeyboardButton(
            product['attributes']['Title'],
            callback_data=product['id'])]
        for product in products
    ]
    keyboard.append([InlineKeyboardButton('Моя корзина', callback_data='Моя корзина')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(text='Привет!', reply_markup=reply_markup)
    return "HANDLE_MENU"


def handle_menu(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    query.answer()
    product_id = query.data
    product, image = get_product_by_id(product_id)
    caption = product['data']['attributes']['Description']
    keyboard = [
        [InlineKeyboardButton('Назад', callback_data='Назад')],
        [InlineKeyboardButton('Добавить в корзину', callback_data=f'Добавить в корзину:{product_id}')],
        [InlineKeyboardButton('Моя корзина', callback_data='Моя корзина')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_photo(
        chat_id,
        photo=image,
        caption=caption,
        reply_markup=reply_markup
    )
    context.bot.delete_message(chat_id, message_id=query.message.message_id)

    return "HANDLE_DESCRIPTION"


def handle_description(update, context):
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        user_reply = update.callback_query.data
    elif update.message:
        chat_id = update.message.chat_id
        user_reply = update.message.text
    else:
        return "START"

    if user_reply == 'Назад':
        products = fetch_products()['data']
        keyboard = [
            [InlineKeyboardButton(
                product['attributes']['Title'],
                callback_data=product['id'])]
            for product in products
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(
            chat_id,
            text='Меню:',
            reply_markup=reply_markup
        )
        return "HANDLE_MENU"
    elif 'Добавить в корзину' in user_reply:
        print(1)
        product_id = user_reply.split(':')[1]
        quantity = 1
        create_or_update_cart(chat_id, {product_id: quantity})
        context.bot.send_message(
            chat_id,
            text='Добавлено!',
        )
        return "HANDLE_MENU"
    else:
        return "START"


def handle_cart(update, context):
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        chat_id = update.message.chat_id
    products = get_cart_by_id(chat_id)
    if not products:
        message = 'Ваша корзина пуста'
    else:
        message = '\n'.join([f'{product} - {info[1]} kg' for product, info in
                             products.items()])

    keyboard = [
        [InlineKeyboardButton(
            f'Удалить {title}',
            callback_data=f'Удалить:{info[0]}')]
        for title, info in products.items()
    ]
    keyboard.append(
        [InlineKeyboardButton('В меню', callback_data='В меню')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id,
        text=message,
        reply_markup=reply_markup
    )
    return "HANDLE_MENU"


def handle_users_reply(update, context):
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    elif user_reply == 'Моя корзина':
        user_state = 'HANDLE_CART'
    elif user_reply == 'В меню':
        products = fetch_products()['data']
        keyboard = [
            [InlineKeyboardButton(
                product['attributes']['Title'],
                callback_data=product['id'])]
            for product in products
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(
            chat_id,
            text='Меню:',
            reply_markup=reply_markup
        )
        return "HANDLE_MENU"
    elif 'Удалить' in user_reply.title():
        cart_product_id = user_reply.split(':')[1]
        delete_cart_product(cart_product_id)
        context.bot.send_message(
            chat_id,
            text='Продукт успешно удален!'
        )
        user_state = 'HANDLE_MENU'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
    }
    state_handler = states_functions[user_state]
    try:
        next_state = state_handler(update, context)
        db.set(chat_id, next_state)
    except Exception as err:
        print(err)


def get_database_connection():
    global _database
    if _database is None:
        database_num = env.str("DB_NUM")
        database_host = env.str("DB_HOST")
        database_port = env.str("DB_PORT")
        _database = redis.Redis(host=database_host, port=database_port,
                                db=database_num)
    return _database


if __name__ == '__main__':
    env = Env()
    env.read_env()
    token = env.str("TG_TOKEN")
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()
    updater.idle()
