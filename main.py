import telebot
from telebot import types

import sqlite3


bot = telebot.TeleBot('TOKEN')

@bot.message_handler(commands=['start'])
def start(message):
    from init_db import init_db
    
    init_db()
    
    
    markup = types.InlineKeyboardMarkup()
    
    mcdonald_btn = types.InlineKeyboardButton("McDonald’s", callback_data='mcdonalds')
    kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
    burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
    tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
    starbucks_btn = types.InlineKeyboardButton("Starbucks", callback_data='starbucks')
    
    markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
    
    bot.send_message(message.chat.id, f'<b>Выберите ресторан из списка или введите название вручную</b>', parse_mode='html', reply_markup=markup)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    from normalize_text import normalize_restaurant
    
    text = message.text.strip()
    restaurant = normalize_restaurant(text)

    if restaurant:
        ask_for_dish(message.chat.id, restaurant) 

    else:
        bot.send_message(message.chat.id, "Выберите ресторан!")


def ask_for_dish(chat_id, restaurant, message_id=None):
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1')
    markup.add(back_btn)

    if message_id:  
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Введите название блюда из <b>{restaurant}</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
    else: 
        bot.send_message(
            chat_id,
            f"Введите название блюда из <b>{restaurant}</b>",
            parse_mode='HTML',
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    bot.answer_callback_query(callback.id)

    if callback.data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'starbucks']:
        from renaming_1 import rename
        dt2 = rename(callback)
        ask_for_dish(callback.message.chat.id, dt2, callback.message.message_id)


    elif callback.data == 'back_1':
        markup = types.InlineKeyboardMarkup()
        mcdonald_btn = types.InlineKeyboardButton("McDonald’s", callback_data='mcdonalds')
        kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
        burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
        tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
        starbucks_btn = types.InlineKeyboardButton("Starbucks", callback_data='starbucks')
        markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)

        bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text='Выберите ресторан из списка или введите название вручную',
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        bot.send_message(callback.message.chat.id, "Выберите ресторан!")



    



bot.polling(none_stop=True)