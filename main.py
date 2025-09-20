import telebot
from telebot import types
import sqlite3
import psycopg2

conn = psycopg2.connect(
    dbname="alamacros",
    user="postgres",
    password="password",
    host="127.0.0.1",
)
cursor = conn.cursor()



bot = telebot.TeleBot('Token')




@bot.message_handler(commands=['start'])
def start(message):
    from init_db import init_db
    # init_db()

    markup = types.InlineKeyboardMarkup()
    mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
    kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
    burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
    tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
    starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
    cart = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')
    
    
    markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
    markup.row(cart)

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
        bot.send_message(message.chat.id, "Этого ресторана нет в базе. Напишите его название в разделе предложений, и мы добавим его в будущем.")
        start(message)


def add_to_cart(user_id, dish_name):
    
    cursor.execute(
        "SELECT weight, kcal, protein, fat, carbs FROM dishes WHERE dish = ?",
        (dish_name,)
    )
    dish = cursor.fetchone()

    if not dish:
        return "❌ Такого блюда нет в базе!"

    weight, kcal, protein, fat, carbs = dish

   
    cursor.execute(
        "SELECT quantity FROM cart_items WHERE user_id = ? AND dish_name = ?",
        (user_id, dish_name)
    )
    result = cursor.fetchone()

    if result:
        
        cursor.execute("""
            UPDATE cart_items 
            SET quantity = quantity + 1,
                weight = weight + ?,
                kcal = kcal + ?,
                protein = protein + ?,
                fat = fat + ?,
                carbs = carbs + ?
            WHERE user_id = ? AND dish_name = ?
        """, (weight, kcal, protein, fat, carbs, user_id, dish_name))
    else:
    
        cursor.execute("""
            INSERT INTO cart_items (user_id, dish_name, quantity, weight, kcal, protein, fat, carbs) 
            VALUES (?, ?, 1, ?, ?, ?, ?, ?)
        """, (user_id, dish_name, weight, kcal, protein, fat, carbs))

    conn.commit()
    return "✅ Блюдо добавлено в корзину"




def get_cart(user_id):
    cursor.execute("""
        SELECT d.name, c.quantity, d.calories, d.proteins, d.fats, d.carbs
        FROM cart_items c
        JOIN dishes d ON c.dish_id = d.id
        WHERE c.user_id=%s
    """, (user_id,))
    return cursor.fetchall()


def clear_cart(user_id):
    cursor.execute("DELETE FROM cart_items WHERE user_id=%s", (user_id,))
    conn.commit()


def get_cart_totals(user_id):
    cursor.execute("""
        SELECT 
            COALESCE(SUM(d.calories * c.quantity),0),
            COALESCE(SUM(d.proteins * c.quantity),0),
            COALESCE(SUM(d.fats * c.quantity),0),
            COALESCE(SUM(d.carbs * c.quantity),0)
        FROM cart_items c
        JOIN dishes d ON c.dish_id = d.id
        WHERE c.user_id=%s
    """, (user_id,))
    return cursor.fetchone()




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

    if callback.data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'tomyumbar']:
        from renaming_1 import rename
        dt2 = rename(callback)
        ask_for_dish(callback.message.chat.id, dt2, callback.message.message_id)

    elif callback.data == 'back_1':
        markup = types.InlineKeyboardMarkup()
        mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
        kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
        burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
        tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
        starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
        cart = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')
        
        markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
        markup.row(cart)

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
        add_dish_to_cart = types.InlineKeyboardButton("🛒 Добавить блюдо в корзину.", callback_data=f"add_dish_to_cart|{restaurant_name}|{dish_name}")
        markup.add(back_btn)
        markup.add(add_dish_to_cart)

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
        
        
        
        
@bot.callback_query_handler(func=lambda callback: True)
def callback_handler_2(callback):
    bot.answer_callback_query(callback.id)
    
    
    user_id = callback.from_user.id
    data = callback.data
    
    if data == "show_cart":
        ls = get_cart(callback.from_user.id)
        bot_answer = ""
        if ls:
            for product, qty in ls:
                bot_answer += f"{product} - {qty} шт."
            bot.send_message(callback.message.chat.id, bot_answer)
        else:
            bot.send_message(callback.message.chat.id, "Ваша корзина пуста")
    if data.startswith("add_dish_to_cart|"):
        _, restaurant_name, dish_name = data.split("|", 2)
        add_to_cart(callback.from_user.id, dish_name)
    
    



    

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
