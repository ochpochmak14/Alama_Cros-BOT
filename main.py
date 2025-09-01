import telebot
from telebot import types
import sqlite3

bot = telebot.TeleBot('TOKEN')



@bot.message_handler(commands=['start'])
def start(message):
    from init_db import init_db
    # init_db()

    markup = types.InlineKeyboardMarkup()
    mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
    kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
    burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
    tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
    starbucks_btn = types.InlineKeyboardButton("Starbucks", callback_data='starbucks')

    markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)

    bot.send_message(message.chat.id,
                     'Выберите ресторан из списка или введите название вручную',
                     parse_mode='html',
                     reply_markup=markup)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    from normalize_text import normalize_restaurant

    text = message.text.strip()
    restaurant = normalize_restaurant(text)

    if restaurant:
        ask_for_dish(message.chat.id, restaurant)
    else:
        bot.send_message(message.chat.id, "Выберите ресторан!")
        start(message)


def ask_for_dish(chat_id, restaurant, message_id=None):
    markup = types.InlineKeyboardMarkup()
    back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1')
    markup.add(back_btn)

    if message_id:
        msg = bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"Введите название блюда из <b>{restaurant}</b>",
            parse_mode='HTML',
            reply_markup=markup
        )
    else:
        msg = bot.send_message(
            chat_id,
            f"Введите название блюда из <b>{restaurant}</b>",
            parse_mode='HTML',
            reply_markup=markup
        )

    bot.register_next_step_handler(msg, dish_handling_func_1, restaurant)


@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    bot.answer_callback_query(callback.id)

    if callback.data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'starbucks']:
        from renaming_1 import rename
        dt2 = rename(callback)
        ask_for_dish(callback.message.chat.id, dt2, callback.message.message_id)

    elif callback.data == 'back_1':
        markup = types.InlineKeyboardMarkup()
        mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
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
    elif "dish|" in callback.data:
        _, restaurant_name, dish_name = callback.data.split("|")
        conn = sqlite3.connect("alamacros.db")
        cur = conn.cursor()

        cur.execute(
            "SELECT weight, kcal, protein, fat, carbs FROM dishes WHERE restaurant = ? AND dish = ?",
            (restaurant_name, dish_name)
        )
        row = cur.fetchone()

        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
        markup.add(back_btn)

        if row:
            weight, kcal, protein, fat, carbs = row
            bot.send_message(
                callback.message.chat.id,
                f"Ресторан - {restaurant_name}\n"
                f"Блюдо - {dish_name}\n"
                f"------------------\n"
                f"Порция: {weight} г\n"
                f"Калории: {kcal}\n"
                f"Белки: {protein} г\n"
                f"Жиры: {fat} г\n"
                f"Углеводы: {carbs} г",
                reply_markup=markup
            )
        else:
            bot.send_message(callback.message.chat.id, "Блюдо не найдено в этом ресторане.", reply_markup=markup)

        cur.close()
        conn.close()


def dish_handling_func_1(message, restaurant):
    from rapidfuzz import process, fuzz
    
    dish_name = message.text.strip()
    restaurant_name = restaurant.strip()

    conn = sqlite3.connect("alamacros.db")
    cur = conn.cursor()

    cur.execute("SELECT dish, weight, kcal, protein, fat, carbs FROM dishes WHERE restaurant = ?", (restaurant_name,))
    all_dishes = cur.fetchall()

    
    
    if not all_dishes:
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
        markup.add(back_btn)
        
        bot.send_message(message.chat.id, "Блюда для этого ресторана не найдены.", reply_markup=markup)
        cur.close()
        conn.close()
        return

    dishes_names = [row[0] for row in all_dishes]
    best_matches = process.extract(dish_name, dishes_names, scorer=fuzz.ratio, limit=5)

    markup = types.InlineKeyboardMarkup()
    added = False

    for match in best_matches:
        name, score, _ = match
        if score >= 50:
            btn = types.InlineKeyboardButton(name, callback_data=f"dish|{restaurant_name}|{name}")
            markup.add(btn)
            added = True

    back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
    markup.add(back_btn)

    if added:
        bot.send_message(message.chat.id, "Похожие блюда:", reply_markup=markup)
    else:
        bot.send_message(
            message.chat.id,
            "Этого блюда нет в базе. Попробуйте ввести другое название или уточнить запрос.",
            reply_markup=markup
        )
        
    cur.close()
    conn.close()



bot.polling(none_stop=True)
