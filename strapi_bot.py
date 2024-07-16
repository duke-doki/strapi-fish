import logging

import redis
from environs import Env
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler, MessageHandler, \
    CommandHandler, Filters

from strapi_fetcher import fetch_products, get_product_by_id, \
    create_or_update_cart, get_cart_products_by_id, delete_cart_product, \
    add_email_to_cart, get_email_by_id

_database = None

logger = logging.getLogger(__name__)


def start(update, context):
    chat_id = update.message.chat_id
    send_menu_setup(context, chat_id)
    return "HANDLE_MENU"


def handle_menu(update, context):
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat_id
        query.answer()
        user_reply = query.data
        if user_reply == 'Моя корзина':
            send_cart_setup(context, chat_id)
            return "HANDLE_CART"
        else:
            product_id = query.data
            product, image = get_product_by_id(product_id)
            caption = product['data']['attributes']['Description']
            keyboard = [
                [InlineKeyboardButton('Назад', callback_data='Назад')],
                [InlineKeyboardButton('Добавить в корзину',
                                      callback_data=f'Добавить в корзину:{product_id}')],
                [InlineKeyboardButton('Моя корзина',
                                      callback_data='Моя корзина')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            context.bot.send_photo(
                chat_id,
                photo=image,
                caption=caption,
                reply_markup=reply_markup
            )
            context.bot.delete_message(chat_id,
                                       message_id=query.message.message_id)
            return "HANDLE_DESCRIPTION"


def handle_description(update, context):
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        user_reply = update.callback_query.data

        if user_reply == 'Назад':
            send_menu_setup(context, chat_id)
            return "HANDLE_MENU"
        elif 'Добавить в корзину' in user_reply:
            product_id = user_reply.split(':')[1]
            context.user_data['product_id'] = product_id
            keyboard = [
                [InlineKeyboardButton(
                    num,
                    callback_data=num)]
                for num in ['1', '5', '10']
            ]
            keyboard.append(
                [
                    InlineKeyboardButton('Моя корзина',
                                         callback_data='Моя корзина'),
                    InlineKeyboardButton('В меню',
                                         callback_data='В меню')
                ],
            )
            reply_markup = InlineKeyboardMarkup(keyboard)
            context.bot.send_message(
                chat_id,
                text='Выберите количество рыбы в кг:',
                reply_markup=reply_markup
            )
            return "HANDLE_QUANTITY"
        elif user_reply == 'Моя корзина':
            send_cart_setup(context, chat_id)
            return "HANDLE_CART"


def handle_quantity(update, context):
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat_id
        query.answer()
        user_reply = query.data
        if user_reply == 'Моя корзина':
            send_cart_setup(context, chat_id)
            return "HANDLE_CART"
        elif user_reply == 'В меню':
            send_menu_setup(context, chat_id)
            return "HANDLE_MENU"
        elif user_reply.isdigit():
            quantity = int(user_reply)
            product_id = context.user_data['product_id']
            create_or_update_cart(chat_id, {product_id: quantity})
            context.bot.send_message(
                chat_id,
                text='Добавлено!',
            )
            send_menu_setup(context, chat_id)
            return "HANDLE_MENU"


def handle_cart(update, context):
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat_id
        query.answer()
        user_reply = query.data
        if user_reply == 'В меню':
            send_menu_setup(context, chat_id)
            return "HANDLE_MENU"
        elif user_reply == 'Оплата':
            context.bot.send_message(
                chat_id,
                text='Пожалуйста, пришлите ваш email'
            )
            return "WAITING_EMAIL"
        elif 'Удалить' in user_reply:
            cart_product_id = user_reply.split(':')[1]
            delete_cart_product(cart_product_id)
            context.bot.send_message(
                chat_id,
                text='Продукт успешно удален!'
            )
            send_menu_setup(context, chat_id)
            return "HANDLE_MENU"


def waiting_email(update, context):
    user_reply = update.message.text
    chat_id = update.message.chat_id
    email_response = add_email_to_cart(chat_id, user_reply)
    if not email_response:
        context.bot.send_message(
            chat_id,
            text='Попробуйте еще раз'
        )
        return "WAITING_EMAIL"
    else:
        email = get_email_by_id(chat_id)
        context.bot.send_message(
            chat_id,
            text=f'Почта {email} успешно сохранена'
        )
        send_menu_setup(context, chat_id)
        return "HANDLE_MENU"


def send_menu_setup(context, chat_id):
    products = fetch_products()['data']
    keyboard = [
        [InlineKeyboardButton(
            product['attributes']['Title'],
            callback_data=product['id'])]
        for product in products
    ]
    keyboard.append(
        [InlineKeyboardButton('Моя корзина',
                              callback_data='Моя корзина')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id,
        text='Меню:',
        reply_markup=reply_markup
    )


def send_cart_setup(context, chat_id):
    products = get_cart_products_by_id(chat_id)
    if not products:
        message = 'Ваша корзина пуста'
    else:
        message = '\n'.join(
            [f'{product} - {info[1]} kg' for product, info in
             products.items()])

    keyboard = [
        [InlineKeyboardButton(
            f'Удалить {title}',
            callback_data=f'Удалить:{info[0]}')]
        for title, info in products.items()
    ]
    keyboard.append(
        [InlineKeyboardButton('В меню', callback_data='В меню')])
    keyboard.append(
        [InlineKeyboardButton('Оплата', callback_data='Оплата')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(
        chat_id,
        text=message,
        reply_markup=reply_markup
    )


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
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_QUANTITY': handle_quantity,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': waiting_email,
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
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
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
