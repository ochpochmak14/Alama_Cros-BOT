import telebot
from telebot import types

import sqlite3


bot = telebot.TeleBot('TOKEN')

@bot.message_handler(commands=['start'])
def start(message):
    
    markup = types.InlineKeyboardMarkup()
    
    mcdonald_btn = types.InlineKeyboardButton("McDonald’s", callback_data='mcdonalds')
    kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
    burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
    tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
    starbucks_btn = types.InlineKeyboardButton("Starbucks", callback_data='starbucks')
    
    markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
    
    bot.send_message(message.chat.id, f'<b>Выберите ресторан из списка или введите название вручную</b>', parse_mode='html', reply_markup=markup)

@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    bot.answer_callback_query(callback.id)
    if callback.data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'starbucks']:
        
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1')
        markup.add(back_btn)
        
        from renaming_1 import rename
        
        dt2 = rename(callback)
            
        
        bot.send_message(callback.message.chat.id, f"Введите название блюда из {dt2}", reply_markup=markup, parse_mode='html')
        bot.delete_message(callback.message.chat.id, callback.message.id)
    elif callback.data == 'back_1':
        start(callback.message)
    
        bot.delete_message(callback.message.chat.id, callback.message.id)
    
    else:
        bot.send_message(callback.message.chat.id, "Выберите ресторан!")
        
    



bot.polling(none_stop=True)