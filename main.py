import telebot
from telebot import types
import sqlite3
import psycopg2


bot = telebot.TeleBot('tok')

DATABASE_URL = "str"

user_dish_map = {}

user_restaurant = {}

RESTAURANT_MAP = {
    "mcdonalds": "McDonald's",
    "bella_ciao": "Bella Ciao",
    "tanuki": "Tanuki",
    "burgerk": "Burger King",
    "kfc": "KFC",
    "tomyumbar": "TomYumBar"
}


def get_conn():
    return psycopg2.connect(DATABASE_URL)



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
    offers_btn = types.InlineKeyboardButton("📝 Раздел предложений", callback_data="offers")
    cats_btn = types.InlineKeyboardButton("📙 Выбор по категориям", callback_data="cats")
    inline_markup.add(mcdonald_btn, popeyes_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
    inline_markup.row(cart)
    inline_markup.row(history_btn)
    inline_markup.row(offers_btn)
    inline_markup.row(cats_btn)

   
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


# @bot.message_handler(content_types=['text'])
# def handle_text(message):
#     from normalize_text import normalize_restaurant

#     text = message.text.strip()
#     restaurant = normalize_restaurant(text)

#     if restaurant:
#         ask_for_dish(message.chat.id, restaurant)
#     else:
#         bot.send_message(message.chat.id, "Этого ресторана нет в базе. Напишите его название в разделе предложений, и мы добавим его в будущем.")
#         start(message)



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
        conn.close()
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
            INSERT INTO cart_items(user_id, dish, restaurant, weight, kcal, protein, fat, carbs)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, dish_name, restaurant, weight, kcal, protein, fat, carbs))

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
            quantity
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
        item_number, restaurant, dish, quantity= row



        text += f"{item_number}. {dish} ({restaurant}) ×{quantity}\n"

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

    if data in ['mcdonalds', 'kfc', 'burgerk', 'tanuki', 'tomyumbar', 'popeyes']:
        from renaming_1 import rename
        dt2 = rename(callback)
        ask_for_dish(callback.message.chat.id, dt2, callback.message.message_id)

    elif data == "history":
        show_history(callback)
    
    elif data == 'back_1':
        start(callback.message)
        # markup = types.InlineKeyboardMarkup()
        # mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data='mcdonalds')
        # popeyes_btn = types.InlineKeyboardButton("POPEYES", callback_data="popeyes")
        # history_btn = types.InlineKeyboardButton("📜 История поиска", callback_data="history")
        # kfc_btn = types.InlineKeyboardButton("KFC", callback_data='kfc')
        # burgerk_btn = types.InlineKeyboardButton("Burger King", callback_data='burgerk')
        # tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data='tanuki')
        # starbucks_btn = types.InlineKeyboardButton("TomYumBar", callback_data='tomyumbar')
        # cart_btn = types.InlineKeyboardButton("🛒 Показать корзину", callback_data='show_cart')
        # markup.add(mcdonald_btn, popeyes_btn, kfc_btn, burgerk_btn, tanuki_btn, starbucks_btn)
        # markup.row(cart_btn)
        # markup.row(history_btn)

        # bot.edit_message_text(
        #     chat_id=callback.message.chat.id,
        #     message_id=callback.message.message_id,
        #     text='Выберите ресторан из списка или введите название вручную',
        #     parse_mode='HTML',
        #     reply_markup=markup
        # )

    elif data.startswith("dish|"):
        _, dishes_id = data.split("|", 1)
        dishes_id = int(dishes_id)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT restaurant, dish, weight, kcal, protein, fat, carbs, allergenes FROM dishes WHERE id = %s",
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
            restaurant_name, dish_name, weight, kcal, protein, fat, carbs, allergenes = row

            allergenes_str = f"Аллергены - {allergenes}"

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
                f"⚠️ {allergenes_str}"
                ,
                reply_markup=markup
            )
            
            add_to_history(user_id, dish_name, restaurant_name)
        else:
            bot.send_message(callback.message.chat.id, "Блюдо не найдено в этом ресторане.", reply_markup=markup)

    elif data == "show_cart":
        ls = get_cart(user_id)
        # print(ls)
        if not ls:
            bot.send_message(callback.message.chat.id, "Ваша корзина пуста")
        else:
            markup = types.InlineKeyboardMarkup()
            del_btn = types.InlineKeyboardButton(text="🚫 Убрать блюдо из корзины", callback_data="del_dish")
            del_cart_btn = types.InlineKeyboardButton(text="❌ Очистить корзину", callback_data="del_cart")
            markup.row(del_btn)
            markup.row(del_cart_btn)
            bot_answer = ls
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
        
        
    elif data == "offers":
        bot.send_message(callback.message.chat.id, """💡 Спасибо за ваши предложения!
Пожалуйста, заполните форму по ссылке ниже 👇""")
        bot.send_message(callback.message.chat.id, "https://docs.google.com/forms/d/e/1FAIpQLScy2RrdUY9-B7U2kOzeXWhjXPOWre5TdfTH5kSnYpQtkfh2xg/viewform?usp=sharing&ouid=105348996454328127243")


    elif data == "cats":
        markup = types.InlineKeyboardMarkup()
        
        btn_bludo = types.InlineKeyboardButton("По блюду 🍽️", callback_data="bludo")
        btn_restaurant = types.InlineKeyboardButton("По ресторану 🏢", callback_data="restaurant")
        
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1')
        
        markup.add(btn_bludo, btn_restaurant)
        markup.row(back_btn)
        msg = bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=f"Выберите способ поиска: 🔍",
            parse_mode='HTML',
            reply_markup=markup
        )
        
        
        
        
        
    elif data == "restaurant":

        markup = types.InlineKeyboardMarkup()
        
        # Кнопки ресторанов
        mcdonald_btn = types.InlineKeyboardButton("McDonald's", callback_data="rest|mcdonalds")
        bella_btn = types.InlineKeyboardButton("Bella Ciao", callback_data="rest|bella_ciao")
        tanuki_btn = types.InlineKeyboardButton("Tanuki", callback_data="rest|tanuki")
        burger_btn = types.InlineKeyboardButton("Burger King", callback_data="rest|burgerk")
        kfc_btn = types.InlineKeyboardButton("KFC", callback_data="rest|kfc")
        tomyum_btn = types.InlineKeyboardButton("TomYumBar", callback_data="rest|tomyumbar")
        
        back_btn = types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1')
        
   
        markup.row(mcdonald_btn, bella_btn, tanuki_btn)
        markup.row(burger_btn, kfc_btn, tomyum_btn)
        markup.row(back_btn)
        
        bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text="Выберите ресторан для поиска блюда 🔍",
            reply_markup=markup
        )

        
    elif data == "bludo":
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("SELECT name FROM sections")
        ls1 = cur.fetchall()  

        markup = types.InlineKeyboardMarkup()
        
        btn1 = types.InlineKeyboardButton("Закуски🍟", callback_data="cat|Закуски")
        btn2 = types.InlineKeyboardButton("Салаты🥗", callback_data="cat|Салаты")
        btn3 = types.InlineKeyboardButton("Паста🍝", callback_data="cat|Паста")
        btn4 = types.InlineKeyboardButton("Горячие блюда🍽️", callback_data="cat|Горячие блюда")
        btn5 = types.InlineKeyboardButton("Бургеры🍔", callback_data="cat|Бургеры")
        btn6 = types.InlineKeyboardButton("Пицца🍕", callback_data="cat|Пицца")
        btn7 = types.InlineKeyboardButton("Суши🍣", callback_data="cat|Суши")
        btn8 = types.InlineKeyboardButton("Десерты🍰", callback_data="cat|Десерты")
        btn9 = types.InlineKeyboardButton("Соусы🥫", callback_data="cat|Соусы")
        btn10 = types.InlineKeyboardButton("Напитки🥤", callback_data="cat|Напитки")
        btn11 = types.InlineKeyboardButton("Завтраки🍳", callback_data="cat|Завтраки")
        btn12 = types.InlineKeyboardButton("Супы🍲", callback_data="cat|Супы")
        
        
        markup.row(btn1, btn2, btn3)      
        markup.row(btn4, btn5, btn6)     
        markup.row(btn7, btn8, btn9)     
        markup.row(btn10, btn11, btn12)   
        
        bot.send_message(callback.message.chat.id, "Выберите категорию блюд:", reply_markup=markup)
    
    
    elif data == "restaurant":
        markup = types.InlineKeyboardMarkup()

        markup.row(
            types.InlineKeyboardButton("McDonald's", callback_data="rest|mcdonalds"),
            types.InlineKeyboardButton("Bella Ciao", callback_data="rest|bella_ciao"),
            types.InlineKeyboardButton("Tanuki", callback_data="rest|tanuki")
        )
        markup.row(
            types.InlineKeyboardButton("Burger King", callback_data="rest|burgerk"),
            types.InlineKeyboardButton("KFC", callback_data="rest|kfc"),
            types.InlineKeyboardButton("TomYumBar", callback_data="rest|tomyumbar")
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_1"))

        bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text="Выберите ресторан для поиска блюда 🔍",
            reply_markup=markup
        )

            
    # elif data.startswith("sort|"):
    #     if data == "sort|ratio":
    #         criterion = "ratio"
    #     elif data == "sort|protein":
    #         criterion = "protein"
    #     elif data == "sort|fat":
    #         criterion = "fat"
    #     elif data == "sort|carbs":
    #         criterion = "carbs"
    #     else:
    #         return

    #     sorted_ids = sort_by(cat_id, criterion)
    #     if not sorted_ids:
    #         bot.send_message(callback.message.chat.id, "Блюд нет 😢")
    #         return

    #     text = "Выберите блюдо для добавления в корзину.\nНапишите номер ⬇️\n\n"
    #     dish_map = {}
    #     counter = 1

    #     conn = get_conn()
    #     cur = conn.cursor()

    #     for dish_id in sorted_ids:
    #         cur.execute(
    #             "SELECT dish, restaurant, kcal, protein, fat, carbs FROM dishes WHERE id = %s",
    #             (dish_id,)
    #         )
    #         row = cur.fetchone()
    #         if not row:
    #             continue

    #         dish_name, restaurant_name, kcal, protein, fat, carbs = row

    #         text += (
    #             f"{counter}. {dish_name} ({restaurant_name})\n"
    #             f"   {kcal} ккал | Б: {protein} г | Ж: {fat} г | У: {carbs} г\n\n"
    #         )

    #         dish_map[counter] = dish_id
    #         counter += 1

    #     cur.close()
    #     conn.close()

      
    #     user_dish_map[callback.message.chat.id] = dish_map

    #     bot.send_message(callback.message.chat.id, text)
        
    elif data.startswith("rest|"):
        call = callback
        bot.answer_callback_query(call.id)

        restaurant = call.data.split("|")[1]
        user_restaurant[call.from_user.id] = restaurant  # сохраняем ресторан

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Лучшее соотношение белков/кбжу", callback_data="sort_rest|ratio"),
        )
        markup.row(
            types.InlineKeyboardButton("Больше всего белка", callback_data="sort_rest|protein"),
            types.InlineKeyboardButton("Меньше всего жиров", callback_data="sort_rest|fat")
        )
        markup.row(
            types.InlineKeyboardButton("Меньше всего углеводов", callback_data="sort_rest|carbs")
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="restaurant"))

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🍽 Ресторан: <b>{restaurant}</b>\nВыберите критерий:",
            parse_mode="HTML",
            reply_markup=markup
        )
        
    elif data.startswith("cat|"):
        global cat_id
        call = callback
        bot.answer_callback_query(call.id) 
        category = call.data.split("|")[1]
        call = callback
        conn = get_conn()
        cur = conn.cursor()

        
        cur.execute("SELECT id FROM sections WHERE name = %s", (category,))
        row = cur.fetchone()
        if not row:
            bot.send_message(call.message.chat.id, "Категория не найдена 😢")
            return
        cat_id = row[0]


        cur.execute("SELECT dish, kcal, protein, fat, carbs FROM dishes WHERE sectionid = %s", (cat_id,))
        ls = cur.fetchall()
        if not ls:
            bot.send_message(call.message.chat.id, "Блюд нет 😢")
            return

        dishes = "\n".join([dish[0] for dish in ls])   

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Лучшее соотношение белков/кбжу", callback_data="sort|ratio"),
        )
        markup.row(
            types.InlineKeyboardButton("Больше всего белка", callback_data="sort|protein"),
            types.InlineKeyboardButton("Меньше всего жиров", callback_data="sort|fat")
        )
        markup.row(
            types.InlineKeyboardButton("Меньше всего углеводов", callback_data="sort|carbs")
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="restaurant"))
         
        bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📂 Категория: <b>{category}</b>\nВыберите критерий сортировки:",
        parse_mode="HTML",
        reply_markup=markup
    )
        
        
    elif data.startswith("sort|"):
        if data == "sort|ratio":
            criterion = "ratio"
        elif data == "sort|protein":
            criterion = "protein"
        elif data == "sort|fat":
            criterion = "fat"
        elif data == "sort|carbs":
            criterion = "carbs"
        else:
            return

        sorted_ids = sort_by(cat_id, criterion)
        if not sorted_ids:
            bot.send_message(callback.message.chat.id, "Блюд нет 😢")
            return

        conn = get_conn()
        cur = conn.cursor()

        text = "🍽 <b>Топ-5 блюд:</b>\n\n"

        for dish_id in sorted_ids:
            cur.execute(
                """
                SELECT dish, restaurant, kcal, protein, fat, carbs
                FROM dishes
                WHERE id = %s
                """,
                (dish_id,)
            )
            row = cur.fetchone()
            if not row:
                continue

            dish_name, restaurant_name, kcal, protein, fat, carbs = row

            text += (
                f"<b>{dish_name}</b> ({restaurant_name})\n"
                f"Б: {protein} г | Ж: {fat} г | У: {carbs} г | {kcal} ккал\n"
                f"🆔 ID: <code>{dish_id}</code>\n"
                f"----------------------\n"
            )

        cur.close()
        conn.close()

        text += "\n👉 Отправьте <b>ID блюда</b>, чтобы добавить в корзину"

        bot.send_message(
            callback.message.chat.id,
            text,
            parse_mode="HTML"
        )

    
    elif data.startswith("sort_rest|"):
        call = callback
        bot.answer_callback_query(call.id)

        criterion = call.data.split("|")[1]
        restaurant = user_restaurant.get(call.from_user.id)

        restaurant_slug = restaurant  # то, что пришло из callback
        restaurant_name = RESTAURANT_MAP.get(restaurant_slug)

        if not restaurant_name:
            bot.send_message(call.message.chat.id, "❌ Неизвестный ресторан")
            return

    
        conn = get_conn()
        cur = conn.cursor()

        if criterion == "ratio":
            order = "(protein * 4.0) / NULLIF(kcal, 0) DESC"
        elif criterion == "protein":
            order = "protein DESC"
        elif criterion == "fat":
            order = "fat ASC"
        elif criterion == "carbs":
            order = "carbs ASC"
        else:
            return

        cur.execute(f"""
            SELECT id, dish, protein, fat, carbs, kcal
            FROM dishes
            WHERE restaurant = %s AND sectionid <> 9 AND sectionid <> 10
            ORDER BY {order}
            LIMIT 5
        """, (restaurant_name,))


        dishes = cur.fetchall()
        conn.close()

        if not dishes:
            bot.send_message(call.message.chat.id, "❌ Блюд не найдено")
            return

        text = "🍽 <b>Топ-5 блюд:</b>\n\n"
        for i, d in enumerate(dishes, 1):
            text += (
                f"{i}. <b>{d[1]}</b>\n"
                f"Б {d[2]}г | Ж {d[3]}г | У {d[4]}г |  {d[5]} ккал\n"
                f"-------\n"
                f"ID: <code>{d[0]}</code>\n\n"
            )

        bot.send_message(
            call.message.chat.id,
            text + "👉 Отправьте ID блюда, чтобы добавить в корзину",
            parse_mode="HTML"
        )



@bot.message_handler(func=lambda message: message.text.isdigit())
def add_by_id(message):
    dish_id = int(message.text)
    result = add_to_cart_by_id(message.from_user.id, dish_id)
    bot.send_message(message.chat.id, result)




# ===== ЛОВИМ ВВОД НОМЕРА =====
@bot.message_handler(content_types=['text'])
def add_by_number(message):
    chat_id = message.chat.id

    if chat_id not in user_dish_map:
        return

    try:
        num = int(message.text.strip())
    except ValueError:
        bot.send_message(chat_id, "❌ Введите номер блюда цифрой!")
        return

    dish_map = user_dish_map[chat_id]

    if num not in dish_map:
        bot.send_message(chat_id, "❌ Такого номера нет в списке!")
        return

    dish_id = dish_map[num]

    result = add_to_cart_by_id(chat_id, dish_id)
    bot.send_message(chat_id, result)

    del user_dish_map[chat_id]
def add_to_cart_by_id(user_id, dish_id):
    conn = None
    cur = None

    try:
        conn = get_conn()
        cur = conn.cursor()

      
        cur.execute("""
            SELECT dish, restaurant, weight, kcal, protein, fat, carbs
            FROM dishes
            WHERE id = %s
        """, (dish_id,))
        row = cur.fetchone()

        if not row:
            return "❌ Блюдо не найдено!"

        dish_name, restaurant_name, weight, kcal, protein, fat, carbs = row

      
        if weight is None:
            weight = 0

        cur.execute("""
            SELECT id
            FROM cart_items
            WHERE user_id = %s AND dish = %s AND restaurant = %s
        """, (user_id, dish_name, restaurant_name))
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
                INSERT INTO cart_items
                (user_id, dish, restaurant, quantity, weight, kcal, protein, fat, carbs)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)
            """, (
                user_id, dish_name, restaurant_name,
                weight, kcal, protein, fat, carbs
            ))

        conn.commit()
        return f"✅ {dish_name} ({restaurant_name}) добавлен в корзину!"

    except Exception as e:
        if conn:
            conn.rollback()
        print("Ошибка add_to_cart_by_id:", e)
        return "❌ Ошибка при добавлении блюда"

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def sort_by(cat_id, criterion):
    conn = get_conn()
    cur = conn.cursor()
    
    if criterion == "protein":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY protein DESC LIMIT 5", (cat_id,))
    elif criterion == "fat":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY fat ASC LIMIT 5", (cat_id,))
    elif criterion == "carbs":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY carbs ASC LIMIT 5", (cat_id,))
    elif criterion == "ratio":
        
        cur.execute("""
    SELECT id, protein*4.0/kcal AS ratio
    FROM dishes
    WHERE sectionid = %s AND kcal > 0
    ORDER BY ratio DESC
    LIMIT 5
""", (cat_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        return []
    
    return [row[0] for row in rows]


@bot.callback_query_handler(func=lambda c: c.data.startswith("cat|"))
def choose_dish(call):
    bot.answer_callback_query(call.id) 
    category = call.data.split("|")[1]
    
    conn = get_conn()
    cur = conn.cursor()

    
    cur.execute("SELECT id FROM sections WHERE name = %s", (category,))
    row = cur.fetchone()
    if not row:
        bot.send_message(call.message.chat.id, "Категория не найдена 😢")
        return
    cat_id = row[0]


    cur.execute("SELECT dish, kcal, protein, fat, carbs FROM dishes WHERE sectionid = %s", (cat_id,))
    ls = cur.fetchall()
    if not ls:
        bot.send_message(call.message.chat.id, "Блюд нет 😢")
        return

    dishes = "\n".join([dish[0] for dish in ls])
    return dishes

def delete_dish(message, user_id):
    conn = get_conn()
    cur = conn.cursor()

    text = message.text.strip()
    bol = all(ch.isdigit() or ch.isspace() for ch in text)

    
    if not bol:
        bot.send_message(message.chat.id, "❌ Нужно ввести число!")
        start(message)
    else:
   
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
        elif score >= 10:
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
                "SELECT dish, restaurant, weight, kcal, protein, fat, carbs, allergenes FROM dishes WHERE id = %s",
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
                dish_name, restaurant_name, weight, kcal, protein, fat, carbs, allergenes = row
                allergenes_str = f"Аллергены - {allergenes}"
                bot.send_message(
                    message.chat.id,
                    f"Ресторан - {restaurant_name}\n"
                    f"Блюдо - {dish_name}\n"
                    f"------------------\n"
                    f"Порция: {weight} г\n"
                    f"Калории: {kcal}\n"
                    f"Белки: {protein} г\n"
                    f"Жиры: {fat} г\n"
                    f"Углеводы: {carbs} г\n"
                    f"⚠️ {allergenes_str}",
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
