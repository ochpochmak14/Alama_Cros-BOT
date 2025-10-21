import telebot
from telebot import types
import sqlite3
import psycopg2


bot = telebot.TeleBot('8257277034:AAFJ4q2HlL6gL0dZcQQ6WvuSUygpTbyeuas')



def get_conn():
    return psycopg2.connect(
        dbname="alamacros",
        user="postgres",
        password="Emin20090",
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
    history_btn = types.InlineKeyboardButton("📜 История поиска", callback_data="history")
    mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
    popeyes_btn = types.InlineKeyboardButton("POPEYES", callback_data="popeyes")
    kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
    burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
    tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
    starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
    cart = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')

    inline_markup.add(mcdonald_btn, popeyes_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
    inline_markup.row(cart)
    inline_markup.row(history_btn)

   
    bot.send_message(
        message.chat.id,
        'Выберите ресторан из списка или введите название вручную',
        parse_mode='HTML',
        reply_markup=inline_markup
    )

    bot.send_message(
        message.chat.id,
        "Используйте кнопки ниже для быстрого доступа 👇",
        reply_markup=reply_markup
    )


@bot.message_handler(func=lambda message: message.text == "📋 Меню")
def show_menu(message):
    start(message)
    
    
@bot.message_handler(func=lambda message: message.text == "🛒 Показать корзину")
def show_menu(message):
    user_id = message.from_user.id

    cart_text = get_cart(user_id)  
    if cart_text == "🛒 Ваша корзина пуста!":
        bot.send_message(message.chat.id, cart_text)
    else:
        
        weight, kcal, protein, fat, carbs = get_cart_totals(user_id)
        totals = f"""Всего:
    Вес - {weight} г.
    Калории - {kcal} ккал.
    Белки - {protein} г.
    Жиры - {fat} г.
    Углеводы - {carbs} г.
"""
        cart_text += totals

        
        markup = types.InlineKeyboardMarkup()
        del_btn = types.InlineKeyboardButton(text="🚫 Убрать блюдо из корзины", callback_data="del_dish")
        del_cart_btn = types.InlineKeyboardButton(text="❌ Очистить корзину", callback_data="del_cart")
        markup.row(del_btn)
        markup.row(del_cart_btn)

        bot.send_message(message.chat.id, cart_text, reply_markup=markup)


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




def add_to_cart(user_id, dish_name, restaurant):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT weight, kcal, protein, fat, carbs, gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus 
        FROM dishes 
        WHERE dish = %s AND restaurant = %s
    """, (dish_name, restaurant))
    dish = cur.fetchone()

    if not dish:
        cur.close()
        conn.close()
        return "❌ Такого блюда в этом ресторане нет!"

    weight, kcal, protein, fat, carbs, gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus = dish
    

    cur.execute("""
        SELECT id, quantity 
        FROM cart_items 
        WHERE user_id = %s AND dish = %s AND restaurant = %s
    """, (user_id, dish_name, restaurant))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE cart_items 
            SET quantity = quantity + 1,
                weight = weight + %s,
                kcal = kcal + %s,
                protein = protein + %s,
                fat = fat + %s,
                carbs = carbs + %s
            WHERE id = %s
        """, (weight, kcal, protein, fat, carbs, existing[0]))
    else:
        cur.execute("""
            INSERT INTO cart_items(user_id, dish, restaurant, weight, kcal, protein, fat, carbs, gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, dish_name, restaurant, weight, kcal, protein, fat, carbs, gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus))

    conn.commit()
    cur.close()
    conn.close()

    return f"✅ {dish_name} ({restaurant}) добавлен в корзину!"







def get_cart(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS item_number,
            restaurant,
            dish,
            quantity,
            gluten,
            sulfites,
            milk,
            sesame,
            egg,
            soy,
            mustard,
            celery,
            fish,
            nuts,
            citrus
        FROM cart_items
        WHERE user_id = %s
        ORDER BY id
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return "🛒 Ваша корзина пуста!"

    text = "🛒 Ваша корзина:\n\n"
    for row in rows:
        (
            item_number, restaurant, dish, quantity,
            gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus
        ) = row

        
        allergens = []
        if gluten not in (None, "", 0): allergens.append("Глютен")
        if sulfites not in (None, "", 0): allergens.append("Сульфиты")
        if milk not in (None, "", 0): allergens.append("Молоко")
        if sesame not in (None, "", 0): allergens.append("Кунжут")
        if egg not in (None, "", 0): allergens.append("Яйцо")
        if soy not in (None, "", 0): allergens.append("Соя")
        if mustard not in (None, "", 0): allergens.append("Горчица")
        if celery not in (None, "", 0): allergens.append("Сельдерей")
        if fish not in (None, "", 0): allergens.append("Рыба")
        if nuts not in (None, "", 0): allergens.append("Орехи")
        if citrus not in (None, "", 0): allergens.append("Цитрусовые")

        allergens_str = f"⚠️ Аллергены: {', '.join(allergens)}" if allergens else "✅ Без аллергенов"

        text += f"{item_number}. {dish} ({restaurant}) ×{quantity}\n"
        text += f"{allergens_str}\n\n"

    return text





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
            COALESCE(SUM(c.weight),0),
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


def get_last_history(user_id, limit=5):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT dish, restaurant 
         FROM search_history 
         WHERE user_id = %s 
         ORDER BY searched_at DESC 
         LIMIT %s""",
        (user_id, limit)
    )
    return cursor.fetchall()  


def add_to_history(user_id, dish_name, restaurant):
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT 1 FROM search_history 
        WHERE user_id = %s AND dish = %s AND restaurant = %s
        """,
        (user_id, dish_name, restaurant)
    )
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute(
            """
            INSERT INTO search_history (user_id, dish, restaurant) 
            VALUES (%s, %s, %s)
            """,
            (user_id, dish_name, restaurant)
        )
        conn.commit()
    
    cursor.close()
    conn.close()



def show_history(callback):
    user_id = callback.from_user.id
    history = get_last_history(user_id)
    
    
    if not history:
        bot.send_message(callback.message.chat.id, "❌ История пуста")
        show_menu(callback.message)
    else:
        markup = types.InlineKeyboardMarkup()
        for dish, restaurant in history:
            conn = get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                        SELECT id FROM dishes
                        WHERE dish = %s AND
                        restaurant = %s
                        """, (dish, restaurant))
            dish_id = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            
            markup.add(types.InlineKeyboardButton(f"{dish} ({restaurant})", callback_data=f"dish|{dish_id}"))
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1')
        markup.row(back_btn)
        bot.send_message(callback.message.chat.id, "📜 История поиска:", reply_markup=markup)



@bot.callback_query_handler(func=lambda callback: True)
def callback_message(callback):
    bot.answer_callback_query(callback.id)
    user_id = callback.from_user.id
    data = callback.data

    if data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'tomyumbar']:
        from renaming_1 import rename
        dt2 = rename(callback)
        ask_for_dish(callback.message.chat.id, dt2, callback.message.message_id)

    elif data == "history":
        show_history(callback)
    
    elif data == 'back_1':
        markup = types.InlineKeyboardMarkup()
        mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
        history_btn = types.InlineKeyboardButton("📜 История поиска", callback_data="history")
        kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
        burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
        tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
        starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
        cart_btn = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')
        markup.add(mcdonald_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
        markup.row(cart_btn)
        markup.row(history_btn)

        bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text='Выберите ресторан из списка или введите название вручную',
            parse_mode='HTML',
            reply_markup=markup
        )

    elif data.startswith("dish|"):
        _, dishes_id = data.split("|", 1)
        dishes_id = int(dishes_id)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT dish, restaurant, weight, kcal, protein, fat, carbs, gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus FROM dishes WHERE id = %s",
            (dishes_id, )
        )
        row = cur.fetchone()

        cur.close()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
        add_btn = types.InlineKeyboardButton(
            "🛒 Добавить блюдо в корзину.",
            callback_data=f"add_dish_to_cart|{dishes_id}"
        )
        markup.add(back_btn)
        markup.row(add_btn)

        if row:
            dish_name, restaurant_name, weight, kcal, protein, fat, carbs, gluten, sulfites, milk, sesame, egg, soy, mustard, celery, fish, nuts, citrus = row
            allergens = []

            if gluten is not None and gluten != "":
                allergens.append("Глютен")
            if sulfites is not None and sulfites != "":
                allergens.append("Сульфиты")
            if milk is not None and milk != "":
                allergens.append("Молоко")
            if sesame is not None and sesame != "":
                allergens.append("Кунжут")
            if egg is not None and egg != "":
                allergens.append("Яйцо")
            if soy is not None and soy != "":
                allergens.append("Соя")
            if mustard is not None and mustard != "":
                allergens.append("Горчица")
            if celery is not None and celery != "":
                allergens.append("Сельдерей")
            if fish is not None and fish != "":
                allergens.append("Рыба")
            if nuts is not None and nuts != "":
                allergens.append("Орехи")
            if citrus is not None and citrus != "":
                allergens.append("Цитрусовые")

            allergens_str = f"Аллергены - {', '.join(allergens)}" if allergens else "Без аллергенов"

            bot.send_message(
                callback.message.chat.id,
                f"Ресторан - {restaurant_name}\n"
                f"Блюдо - {dish_name}\n"
                f"------------------\n"
                f"Порция: {weight} г\n"
                f"Калории: {kcal}\n"
                f"Белки: {protein} г\n"
                f"Жиры: {fat} г\n"
                f"Углеводы: {carbs} г\n"
                f"------------------\n"
                f"⚠️{allergens_str}"
                ,
                reply_markup=markup
            )
            
            add_to_history(user_id, dish_name, restaurant_name)
        else:
            bot.send_message(callback.message.chat.id, "Блюдо не найдено в этом ресторане.", reply_markup=markup)

    elif data == "show_cart":
        ls = list(get_cart(user_id))
        if not ls:
            bot.send_message(callback.message.chat.id, "Ваша корзина пуста")
        else:
            markup = types.InlineKeyboardMarkup()
            del_btn = types.InlineKeyboardButton(text="🚫 Убрать блюдо из корзины", callback_data="del_dish")
            del_cart_btn = types.InlineKeyboardButton(text="❌ Очистить корзину", callback_data="del_cart")
            markup.row(del_btn)
            markup.row(del_cart_btn)
            bot_answer = "\n".join(f"{id}.{restaurant} — {product} - {qty} шт."
                                   for id, restaurant, product, qty in ls)
            bot_answer += "\n\n"
            
            res = get_cart_totals(callback.from_user.id)
            weight, kcal, protein, fat, carbs = res
            bot_answer += f"""Всего:
            Вес - {weight} г.
            Каллории - {kcal} ккал.
            Белки - {protein} г.
            Жиры - {fat} г.
            Углеводы - {carbs} г. 
            """
            bot.send_message(callback.message.chat.id, bot_answer, reply_markup=markup)

    elif data.startswith("add_dish_to_cart|"):
        _, dishes_id = data.split("|", 1)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT dish, restaurant FROM dishes WHERE id = %s", (dishes_id, ))
        result = cur.fetchone()
        dish_name, restaurant_name = result
        add_to_cart(user_id, dish_name, restaurant_name)
        bot.send_message(
            callback.message.chat.id,
            f"✅ Блюдо '{dish_name}' из {restaurant_name} добавлено в корзину"
        )
    elif data == "del_cart":
        clear_cart(callback.from_user.id)
        bot.send_message(callback.message.chat.id, "✅ Ваша корзина успешно очищена!")
    elif data == "del_dish":
        msg1 = bot.send_message(callback.message.chat.id, "✏️ Введите номер блюда и количество порций, которые хотите удалить ЧЕРЕЗ ПРОБЕЛ")
        bot.register_next_step_handler(msg1, delete_dish, callback.from_user.id)

        
    
def delete_dish(message, user_id):
    conn = get_conn()
    cur = conn.cursor()

   
    item_number, qty_to_remove = message.text.strip().split()
    item_number = int(item_number)
    qty_to_remove = int(qty_to_remove)

    
    cur.execute("""
        SELECT id, dish
        FROM (
            SELECT 
                id,
                dish,
                ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
            FROM cart_items
            WHERE user_id = %s
        ) t
        WHERE rn = %s
    """, (user_id, item_number))
    res1 = cur.fetchone()

    if not res1:
        bot.send_message(message.chat.id, f"❌ В корзине нет блюда №{item_number}")
        cur.close()
        conn.close()
        return

    real_id, dish_name = res1

   
    cur.execute("SELECT weight, kcal, protein, fat, carbs FROM dishes WHERE dish = %s", (dish_name,))
    res2 = cur.fetchone()
    weight, kcal_per_portion, protein_per_portion, fat_per_portion, carbs_per_portion = res2

   
    delta_weight = qty_to_remove * float(weight)
    delta_kcal = qty_to_remove * float(kcal_per_portion)
    delta_protein = qty_to_remove * float(protein_per_portion)
    delta_fat = qty_to_remove * float(fat_per_portion)
    delta_carbs = qty_to_remove * float(carbs_per_portion)

  
    cur.execute("""
        UPDATE cart_items
        SET 
            weight = weight - %s,
            quantity = quantity - %s,
            kcal = kcal - %s,
            protein = protein - %s,
            fat = fat - %s,
            carbs = carbs - %s
        WHERE id = %s AND user_id = %s
        RETURNING quantity;
    """, (
        delta_weight, qty_to_remove,
        delta_kcal, delta_protein,
        delta_fat, delta_carbs,
        real_id, user_id
    ))

    
    cur.execute("""
        DELETE FROM cart_items
        WHERE id = %s AND user_id = %s AND quantity <= 0
    """, (real_id, user_id))

    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Блюдо №{item_number} удалено из корзины!")

def dish_handling_func_1(message, restaurant):
    from rapidfuzz import process, fuzz

    dish_name = message.text.strip()
    restaurant_name = restaurant.strip()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT dish, weight, kcal, protein, fat, carbs FROM dishes WHERE restaurant = %s",
        (restaurant_name,)
    )
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
    dishes_map = {name.lower(): name for name in dishes_names}

    best_matches = process.extract(
        dish_name.lower(),
        list(dishes_map.keys()),
        scorer=fuzz.ratio,
        limit=5
    )
    best_matches = [(dishes_map[name], score, idx) for name, score, idx in best_matches]

    markup = types.InlineKeyboardMarkup()
    added = False
    exist = False
    dish_name2 = None

    for match in best_matches:
        name, score, _ = match
        if score >= 99:
            exist = True
            dish_name2 = name
        elif score >= 50:
            cur.execute("SELECT id FROM dishes WHERE restaurant = %s AND dish = %s", (restaurant_name, name))
            res = cur.fetchone()
            if res:
                btn = types.InlineKeyboardButton(name, callback_data=f"dish|{res[0]}")
                markup.add(btn)
                added = True

    back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
    markup.add(back_btn)

    if exist:
        cur.execute("SELECT id FROM dishes WHERE restaurant = %s AND dish = %s", (restaurant_name, dish_name2))
        res = cur.fetchone()
        if res:
            dishes_id = res[0]
            cur.execute(
                "SELECT dish, restaurant, weight, kcal, protein, fat, carbs FROM dishes WHERE id = %s",
                (dishes_id,)
            )
            row = cur.fetchone()

            cur.close()
            conn.close()

            markup = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1')
            add_btn = types.InlineKeyboardButton(
                "🛒 Добавить блюдо в корзину.",
                callback_data=f"add_dish_to_cart|{dishes_id}"
            )
            markup.add(back_btn)
            markup.row(add_btn)

            if row:
                dish_name, restaurant_name, weight, kcal, protein, fat, carbs = row
                bot.send_message(
                    message.chat.id,
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
                add_to_history(message.from_user.id, dish_name, restaurant_name)
    elif added:
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
