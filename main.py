import telebot
from telebot import types
import sqlite3
import psycopg2


bot = telebot.TeleBot('TOKEN')



def get_conn():
    return psycopg2.connect(
        dbname="alamacros",
        user="postgres",
        password="ПАРОЛЬ",
        host="127.0.0.1",
        port="5432"
    )



@bot.message_handler(commands=['start'])
def start(message):
    bot.clear_step_handler_by_chat_id(message.chat.id)

    reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu_btn = types.KeyboardButton("📋 Меню")
    cart_btn = types.KeyboardButton("🛒 Показать корзину")
    reply_markup.add(menu_btn, cart_btn)

    
    inline_markup = types.InlineKeyboardMarkup()
    mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
    kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
    burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
    tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
    starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
    cart = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')

    inline_markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
    inline_markup.row(cart)

   
    bot.send_message(
        message.chat.id,
        'Выберите ресторан из списка или введите название вручную',
        parse_mode='HTML',
        reply_markup=inline_markup
    )

    bot.send_message(
        message.chat.id,
        "Используй кнопки ниже для быстрого доступа 👇",
        reply_markup=reply_markup
    )


@bot.message_handler(func=lambda message: message.text == "📋 Меню")
def show_menu(message):
    start(message)
    
    
@bot.message_handler(func=lambda message: message.text == "🛒 Показать корзину")
def show_menu(message):
    user_id = message.from_user.id

    ls = list(get_cart(user_id))
    if not ls:
        bot.send_message(message.chat.id, "Ваша корзина пуста")
    else:
        bot_answer = "\n".join(f"{restaurant} — {product} - {qty} шт."
                                   for restaurant, product, qty in ls)
        bot_answer += "\n\n"
            
        res = get_cart_totals(message.from_user.id)
        kcal, protein, fat, carbs = res
        bot_answer += f"""Всего:
            Каллории - {kcal} ккал.
            Белки - {protein} г.
            Жиры - {fat} г.
            Углеводы - {carbs} г. """
        bot.send_message(message.chat.id, bot_answer)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    from normalize_text import normalize_restaurant

    text = message.text.strip()
    restaurant = normalize_restaurant(text)

    if restaurant:
        ask_for_dish(message.chat.id, restaurant)
    if text == "📋 Меню":
        pass
    else:
        bot.send_message(message.chat.id, "Этого ресторана нет в базе. Напишите его название в разделе предложений, и мы добавим его в будущем.")
        start(message)


def add_to_cart(user_id, dish_name, restaurant):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT weight, kcal, protein, fat, carbs 
        FROM dishes 
        WHERE dish = %s AND restaurant = %s
    """, (dish_name, restaurant))
    dish = cur.fetchone()

    if not dish:
        cur.close()
        return "❌ Такого блюда в этом ресторане нет!"

    weight, kcal, protein, fat, carbs = dish

    cur.execute("""
        SELECT id, quantity 
        FROM cart_items 
        WHERE user_id = %s AND dish = %s AND restaurant = %s
    """, (user_id, dish_name, restaurant))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE cart_items 
            SET quantity = quantity + 1 
            WHERE id = %s
        """, (existing[0],))
    else:
        cur.execute("""
            INSERT INTO cart_items(user_id, dish, restaurant, weight, kcal, protein, fat, carbs, quantity)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1)
        """, (user_id, dish_name, restaurant, weight, kcal, protein, fat, carbs))

    conn.commit()
    cur.close()

    return f"✅ {dish_name} ({restaurant}) добавлен в корзину!"






def get_cart(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT restaurant, dish, quantity FROM cart_items WHERE user_id = %s", (user_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows



def clear_cart(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def get_cart_totals(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COALESCE(SUM(c.kcal),0),
            COALESCE(SUM(c.protein),0),
            COALESCE(SUM(c.fat),0),
            COALESCE(SUM(c.carbs),0)
        FROM cart_items c
        WHERE c.user_id = %s
    """, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result





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
    user_id = callback.from_user.id
    data = callback.data

    if data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'tomyumbar']:
        from renaming_1 import rename
        dt2 = rename(callback)
        ask_for_dish(callback.message.chat.id, dt2, callback.message.message_id)

    elif data == 'back_1':
        markup = types.InlineKeyboardMarkup()
        mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
        kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
        burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
        tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
        starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
        cart_btn = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')
        markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
        markup.row(cart_btn)

        bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text='Выберите ресторан из списка или введите название вручную',
            parse_mode='HTML',
            reply_markup=markup
        )

    elif data.startswith("dish|"):
        _, restaurant_name, dish_name = data.split("|")

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT weight, kcal, protein, fat, carbs FROM dishes WHERE restaurant = %s AND dish = %s",
            (restaurant_name, dish_name)
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
        add_btn = types.InlineKeyboardButton(
            "🛒 Добавить блюдо в корзину.",
            callback_data=f"add_dish_to_cart|{restaurant_name}|{dish_name}"
        )
        markup.add(back_btn)
        markup.row(add_btn)

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

    elif data == "show_cart":
        ls = list(get_cart(user_id))
        if not ls:
            bot.send_message(callback.message.chat.id, "Ваша корзина пуста")
        else:
            bot_answer = "\n".join(f"{restaurant} — {product} - {qty} шт."
                                   for restaurant, product, qty in ls)
            bot_answer += "\n\n"
            
            res = get_cart_totals(callback.from_user.id)
            kcal, protein, fat, carbs = res
            bot_answer += f"""Всего:
            Каллории - {kcal} ккал.
            Белки - {protein} г.
            Жиры - {fat} г.
            Углеводы - {carbs} г. """
            bot.send_message(callback.message.chat.id, bot_answer)

    elif data.startswith("add_dish_to_cart|"):
        _, restaurant_name, dish_name = data.split("|", 2)
        add_to_cart(user_id, dish_name, restaurant_name)
        bot.send_message(
            callback.message.chat.id,
            f"✅ Блюдо '{dish_name}' из {restaurant_name} добавлено в корзину"
        )


        
    

    

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
