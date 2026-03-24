import telebot
from telebot import types
import psycopg2
import os

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
DATABASE_URL = os.getenv("DATABASE_URL")

# ─── ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ────────────────────────────────────────────────────

user_dish_map = {}
user_restaurant = {}   # для сортировки по ресторану в категориях
user_state = {}        # для ожидания ввода ID блюда
user_last_restaurant = {}  # для кнопки «Назад» — возврат в тот же ресторан

cat_id = None  # текущая категория (глобальная — TODO: перенести в user_state)

RESTAURANT_MAP = {
    "mcdonalds":  "McDonald's",
    "bella_ciao": "Bella Ciao",
    "tanuki":     "Tanuki",
    "burgerk":    "Burger King",
    "kfc":        "KFC",
    "tomyumbar":  "TomYumBar",
    "popeyes":    "Popeyes",
    "Додо пицца": "Додо пицца",
    "bahandi":    "Баханди",
    "coffeeboom": "Кофе Бум",
}


# ─── БД ───────────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DATABASE_URL)


# ─── ФОРМАТИРОВАНИЕ КАРТОЧКИ БЛЮДА ────────────────────────────────────────────

def format_dish_message(row):
    """
    row = (dish_name, restaurant_name, weight, kcal, protein, fat, carbs,
           allergenes, suspicious_kbju, suspicious_text)
    """
    dish_name, restaurant_name, weight, kcal, protein, fat, carbs, \
        allergenes, suspicious_kbju, suspicious_text = row

    if allergenes is None:
        allergenes = "Информация об аллергенах не опубликована производителем."
    allergenes_str = f"Аллергены - {allergenes}"

    website = ""
    if restaurant_name == "Додо пицца":
        website = "Ознакомиться со всеми аллергенами: https://drive.google.com/file/d/1GWaKPdU7t5URgMkh_X4pJqmyZuGr9FdQ/view"
    elif restaurant_name == "McDonald's":
        website = "Ознакомиться со всеми аллергенами: https://im.kz/products"
    elif restaurant_name == "Tanuki":
        website = "Ознакомиться со всеми аллергенами: https://tanukifamily.kz/tanuki_kz/almaty/"
    elif restaurant_name == "Hardee's":
        website = "Ознакомиться со всеми аллергенами: https://drive.google.com/file/d/1U_9uKD4QqIVHrp7z4XEq9b3Yuls6orKV/view?usp=sharing"

    if weight is None:
        weight = "Отсутствуют данные, уточните пожалуйста у ресторана."

    text = (
        f"Ресторан - {restaurant_name}\n"
        f"Блюдо - {dish_name}\n"
        f"------------------\n"
        f"Порция: {weight} г\n"
        f"Калории: {kcal}\n"
        f"Белки: {protein} г\n"
        f"Жиры: {fat} г\n"
        f"Углеводы: {carbs} г\n"
        f"------------------\n"
        f"{website}\n"
        f"⚠️ {allergenes_str}"
    )

    if suspicious_kbju and suspicious_text:
        text += f"\n\n🚨 <b>Внимание!</b> {suspicious_text}"

    return text


# ─── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────

def build_main_inline_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("McDonald's",  callback_data='mcdonalds'),
        types.InlineKeyboardButton("POPEYES",     callback_data='popeyes'),
        types.InlineKeyboardButton("KFC",         callback_data='kfc'),
    )
    markup.row(
        types.InlineKeyboardButton("Burger King", callback_data='burgerk'),
        types.InlineKeyboardButton("Tanuki",      callback_data='tanuki'),
        types.InlineKeyboardButton("TomYumBar",   callback_data='tomyumbar'),
    )
    # Баханди и Кофе Бум — только через "По ресторану" или текстом
    markup.row(types.InlineKeyboardButton("🥤 Универсальные напитки", callback_data='universal_drinks'))
    markup.row(types.InlineKeyboardButton("🛒 Показать корзину",      callback_data='show_cart'))
    markup.row(types.InlineKeyboardButton("📜 История поиска",        callback_data='history'))
    markup.row(types.InlineKeyboardButton("📝 Раздел предложений",    callback_data='offers'))
    markup.row(types.InlineKeyboardButton("📙 Выбор по категориям",   callback_data='cats'))
    return markup


def send_main_menu(chat_id):
    reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    reply_markup.add(
        types.KeyboardButton("📋 Меню"),
        types.KeyboardButton("🛒 Показать корзину")
    )
    bot.send_message(
        chat_id,
        'Выберите ресторан из списка или введите название вручную',
        parse_mode='HTML',
        reply_markup=build_main_inline_markup()
    )
    bot.send_message(
        chat_id,
        "Используйте кнопки ниже для быстрого доступа 👇",
        reply_markup=reply_markup
    )


def show_menu1(chat_id, user_id):
    bot.clear_step_handler_by_chat_id(chat_id=chat_id)
    send_main_menu(chat_id)


# ─── СТАРТ ────────────────────────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT accepted FROM user_agreements WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row or row[0] == 0:
        send_agreement(user_id, chat_id)
        return

    bot.clear_step_handler_by_chat_id(chat_id)
    send_main_menu(chat_id)


@bot.message_handler(func=lambda m: m.text == "📋 Меню")
def show_menu(message):
    bot.clear_step_handler_by_chat_id(chat_id=message.chat.id)
    send_main_menu(message.chat.id)


# ─── СОГЛАШЕНИЕ ───────────────────────────────────────────────────────────────

def send_agreement(user_id, chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Согласен",    callback_data="agree_yes"),
        types.InlineKeyboardButton("❌ Не согласен", callback_data="agree_no")
    )
    with open("Пользовательское соглашение.docx", "rb") as f:
        bot.send_document(
            chat_id,
            document=f,
            caption="📄 Пользовательское соглашение\n\nПожалуйста, ознакомьтесь и подтвердите согласие.",
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda c: c.data in ("agree_yes", "agree_no"))
def agreement_handler(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "agree_yes":
        set_agreement(user_id, True)
        bot.send_message(chat_id, "✅ Спасибо! Вы приняли пользовательское соглашение.")
        fake_message = call.message
        fake_message.from_user = call.from_user
        start(fake_message)
    else:
        bot.send_message(chat_id, "❌ Без принятия соглашения бот недоступен.")


def set_agreement(user_id, accepted: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_agreements (user_id, accepted)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET accepted = EXCLUDED.accepted, accepted_at = NOW()
    """, (user_id, int(accepted)))
    conn.commit()
    cur.close()
    conn.close()


# ─── КОРЗИНА ──────────────────────────────────────────────────────────────────

def add_to_cart(user_id, dish_name, restaurant):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT weight, kcal, protein, fat, carbs
        FROM dishes WHERE dish = %s AND restaurant = %s
    """, (dish_name, restaurant))
    dish = cur.fetchone()

    if not dish:
        cur.close()
        conn.close()
        return "❌ Такого блюда в этом ресторане нет!"

    weight, kcal, protein, fat, carbs = dish

    cur.execute("""
        SELECT id FROM cart_items
        WHERE user_id = %s AND dish = %s AND restaurant = %s
    """, (user_id, dish_name, restaurant))
    existing = cur.fetchone()

    if existing:
        cur.execute("""
            UPDATE cart_items
            SET quantity  = quantity + 1,
                weight    = weight   + %s,
                kcal      = kcal     + %s,
                protein   = protein  + %s,
                fat       = fat      + %s,
                carbs     = carbs    + %s
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


def add_to_cart_by_id(user_id, dish_id):
    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT dish, restaurant, weight, kcal, protein, fat, carbs
            FROM dishes WHERE id = %s
        """, (dish_id,))
        row = cur.fetchone()

        if not row:
            return "❌ Блюдо не найдено!"

        dish_name, restaurant_name, weight, kcal, protein, fat, carbs = row
        if weight is None:
            weight = 0

        cur.execute("""
            SELECT id FROM cart_items
            WHERE user_id = %s AND dish = %s AND restaurant = %s
        """, (user_id, dish_name, restaurant_name))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE cart_items
                SET quantity = quantity + 1,
                    weight   = weight   + %s,
                    kcal     = kcal     + %s,
                    protein  = protein  + %s,
                    fat      = fat      + %s,
                    carbs    = carbs    + %s
                WHERE id = %s
            """, (weight, kcal, protein, fat, carbs, existing[0]))
        else:
            cur.execute("""
                INSERT INTO cart_items
                (user_id, dish, restaurant, quantity, weight, kcal, protein, fat, carbs)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)
            """, (user_id, dish_name, restaurant_name, weight, kcal, protein, fat, carbs))

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


def get_cart(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS item_number,
            restaurant, dish, quantity
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
    for item_number, restaurant, dish, quantity in rows:
        text += f"{item_number}. {dish} ({restaurant}) ×{quantity}\n"
    return text


def get_cart_totals(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COALESCE(SUM(weight), 0),
            COALESCE(SUM(kcal),   0),
            COALESCE(SUM(protein),0),
            COALESCE(SUM(fat),    0),
            COALESCE(SUM(carbs),  0)
        FROM cart_items
        WHERE user_id = %s
    """, (user_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result


def clear_cart(user_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()


def _send_cart(chat_id, user_id):
    """Вспомогательная — отправить корзину с итогами и кнопками."""
    cart_text = get_cart(user_id)
    if cart_text == "🛒 Ваша корзина пуста!":
        bot.send_message(chat_id, cart_text)
        return
    weight, kcal, protein, fat, carbs = get_cart_totals(user_id)
    cart_text += (
        f"\nВсего:\n"
        f"    Вес       - {weight} г.\n"
        f"    Калории   - {kcal} ккал.\n"
        f"    Белки     - {protein} г.\n"
        f"    Жиры      - {fat} г.\n"
        f"    Углеводы  - {carbs} г.\n"
    )
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🚫 Убрать блюдо из корзины", callback_data="del_dish"))
    markup.row(types.InlineKeyboardButton("❌ Очистить корзину",         callback_data="del_cart"))
    bot.send_message(chat_id, cart_text, reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "🛒 Показать корзину")
def handle_show_cart(message):
    _send_cart(message.chat.id, message.from_user.id)


# ─── УНИВЕРСАЛЬНЫЕ НАПИТКИ ────────────────────────────────────────────────────

def show_universal_drinks(chat_id):
    """Показывает список универсальных напитков из таблицы universal_drinks."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT name, volume_ml, kcal, protein, fat, carbs
        FROM universal_drinks
        ORDER BY name, volume_ml
    """)
    drinks = cur.fetchall()
    cur.close()
    conn.close()

    if not drinks:
        bot.send_message(chat_id, "❌ Данные о напитках пока не загружены.")
        return

    text = "🥤 <b>Универсальные напитки:</b>\n<i>Одинаковы во всех ресторанах</i>\n\n"
    for name, volume, kcal, protein, fat, carbs in drinks:
        text += (
            f"<b>{name}</b> {volume} мл\n"
            f"Калории: {kcal} ккал | Б: {protein} г | Ж: {fat} г | У: {carbs} г\n"
            f"─────────────\n"
        )

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_1"))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)


# ─── ВВОД БЛЮДА ───────────────────────────────────────────────────────────────

def _get_back_cb(restaurant_name):
    """Возвращает callback_data для кнопки Назад — в тот же ресторан."""
    for k, v in RESTAURANT_MAP.items():
        if v == restaurant_name:
            return f"back_rest|{k}"
    return "back_1"


def ask_for_dish(chat_id, restaurant, message_id=None):
    markup = types.InlineKeyboardMarkup()
    back_cb = _get_back_cb(restaurant) if restaurant else "back_1"
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data=back_cb))

    text = f"Введите название блюда из <b>{restaurant}</b>" if restaurant else "❌ Некорректный ресторан"

    if message_id:
        msg = bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=text, parse_mode='HTML', reply_markup=markup
        )
    else:
        msg = bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)

    if restaurant:
        bot.register_next_step_handler(msg, dish_handling_func_1, restaurant)


# ─── ИСТОРИЯ ──────────────────────────────────────────────────────────────────

def get_last_history(user_id, limit=5):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT dish, restaurant FROM search_history WHERE user_id = %s ORDER BY searched_at DESC LIMIT %s",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def add_to_history(user_id, dish_name, restaurant):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM search_history WHERE user_id = %s AND dish = %s AND restaurant = %s",
        (user_id, dish_name, restaurant)
    )
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO search_history (user_id, dish, restaurant) VALUES (%s, %s, %s)",
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
        send_main_menu(callback.message.chat.id)
        return

    markup = types.InlineKeyboardMarkup()
    conn = get_conn()
    cursor = conn.cursor()
    for dish, restaurant in history:
        cursor.execute(
            "SELECT id FROM dishes WHERE dish = %s AND restaurant = %s",
            (dish, restaurant)
        )
        res = cursor.fetchone()
        if res:
            markup.add(types.InlineKeyboardButton(
                f"{dish} ({restaurant})", callback_data=f"dish|{res[0]}"
            ))
    cursor.close()
    conn.close()
    markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1'))
    bot.send_message(callback.message.chat.id, "📜 История поиска:", reply_markup=markup)


# ─── СОРТИРОВКА ───────────────────────────────────────────────────────────────

def sort_by(section_id, criterion):
    conn = get_conn()
    cur = conn.cursor()
    if criterion == "protein":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY protein DESC LIMIT 5", (section_id,))
    elif criterion == "fat":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY fat ASC LIMIT 5", (section_id,))
    elif criterion == "carbs":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY carbs ASC LIMIT 5", (section_id,))
    elif criterion == "ratio":
        cur.execute("""
            SELECT id FROM dishes
            WHERE sectionid = %s AND kcal > 0
            ORDER BY protein * 4.0 / kcal DESC
            LIMIT 5
        """, (section_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]


# ─── ГЛАВНЫЙ CALLBACK ХЕНДЛЕР ─────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: True)
def callback_message(callback):
    bot.answer_callback_query(callback.id)
    user_id = callback.from_user.id
    data = callback.data
    chat_id = callback.message.chat.id

    # ── Выбор ресторана из главного меню ──────────────────────────────────────
    if data in RESTAURANT_MAP:
        from renaming_1 import rename
        dt2 = rename(callback)
        user_last_restaurant[user_id] = dt2
        ask_for_dish(chat_id, dt2)

    # ── Универсальные напитки ─────────────────────────────────────────────────
    elif data == "universal_drinks":
        show_universal_drinks(chat_id)

    # ── История ───────────────────────────────────────────────────────────────
    elif data == "history":
        show_history(callback)

    # ── Назад в главное меню ──────────────────────────────────────────────────
    elif data == "back_1":
        show_menu1(chat_id, user_id)

    # ── Назад в тот же ресторан ───────────────────────────────────────────────
    elif data.startswith("back_rest|"):
        rest_key = data.split("|", 1)[1]
        restaurant_name = RESTAURANT_MAP.get(rest_key)
        if restaurant_name:
            user_last_restaurant[user_id] = restaurant_name
            ask_for_dish(chat_id, restaurant_name)
        else:
            show_menu1(chat_id, user_id)

    # ── Карточка блюда ────────────────────────────────────────────────────────
    elif data.startswith("dish|"):
        _, dishes_id = data.split("|", 1)
        dishes_id = int(dishes_id)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT dish, restaurant, weight, kcal, protein, fat, carbs,
                   allergenes, suspicious_kbju, suspicious_text
            FROM dishes WHERE id = %s
        """, (dishes_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data='back_1'))
        markup.row(types.InlineKeyboardButton(
            "🛒 Добавить блюдо в корзину.",
            callback_data=f"add_dish_to_cart|{dishes_id}"
        ))

        if row:
            text = format_dish_message(row)
            bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
            add_to_history(user_id, row[0], row[1])
        else:
            bot.send_message(chat_id, "Блюдо не найдено.", reply_markup=markup)

    # ── Корзина ───────────────────────────────────────────────────────────────
    elif data == "show_cart":
        _send_cart(chat_id, user_id)

    elif data.startswith("add_dish_to_cart|"):
        _, dishes_id = data.split("|", 1)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT dish, restaurant FROM dishes WHERE id = %s", (dishes_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            dish_name, restaurant_name = result
            msg = add_to_cart(user_id, dish_name, restaurant_name)
            bot.send_message(chat_id, msg)

    elif data == "del_cart":
        clear_cart(user_id)
        bot.send_message(chat_id, "✅ Ваша корзина успешно очищена!")

    elif data == "del_dish":
        msg1 = bot.send_message(
            chat_id,
            "✏️ Введите номер блюда и количество порций, которые хотите удалить ЧЕРЕЗ ПРОБЕЛ"
        )
        bot.register_next_step_handler(msg1, delete_dish, user_id)

    # ── Предложения ───────────────────────────────────────────────────────────
    elif data == "offers":
        bot.send_message(chat_id, "💡 Спасибо за ваши предложения!\nПожалуйста, заполните форму по ссылке ниже 👇")
        bot.send_message(chat_id, "https://docs.google.com/forms/d/e/1FAIpQLScy2RrdUY9-B7U2kOzeXWhjXPOWre5TdfTH5kSnYpQtkfh2xg/viewform?usp=sharing&ouid=105348996454328127243")

    # ── Выбор по категориям ───────────────────────────────────────────────────
    elif data == "cats":
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("По блюду 🍽️",     callback_data="bludo"),
            types.InlineKeyboardButton("По ресторану 🏢", callback_data="restaurant")
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1'))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text="Выберите способ поиска: 🔍",
            parse_mode='HTML',
            reply_markup=markup
        )

    # ── По ресторану ──────────────────────────────────────────────────────────
    elif data == "restaurant":
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("McDonald's",  callback_data="rest|mcdonalds"),
            types.InlineKeyboardButton("Bella Ciao",  callback_data="rest|bella_ciao"),
            types.InlineKeyboardButton("Tanuki",      callback_data="rest|tanuki")
        )
        markup.row(
            types.InlineKeyboardButton("Burger King", callback_data="rest|burgerk"),
            types.InlineKeyboardButton("KFC",         callback_data="rest|kfc"),
            types.InlineKeyboardButton("TomYumBar",   callback_data="rest|tomyumbar")
        )
        markup.row(
            types.InlineKeyboardButton("Popeyes",     callback_data="rest|popeyes"),
            types.InlineKeyboardButton("Додо пицца",  callback_data="rest|Додо пицца")
        )
        markup.row(
            types.InlineKeyboardButton("Баханди",     callback_data="rest|bahandi"),
            types.InlineKeyboardButton("Кофе Бум",    callback_data="rest|coffeeboom")
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1'))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text="Выберите ресторан для поиска блюда 🔍",
            reply_markup=markup
        )

    # ── По блюду (категории) ──────────────────────────────────────────────────
    elif data == "bludo":
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("Закуски🍟",        callback_data="cat|Закуски"),
            types.InlineKeyboardButton("Салаты🥗",         callback_data="cat|Салаты"),
            types.InlineKeyboardButton("Паста🍝",          callback_data="cat|Паста")
        )
        markup.row(
            types.InlineKeyboardButton("Горячие блюда🍽️", callback_data="cat|Горячие блюда"),
            types.InlineKeyboardButton("Бургеры🍔",        callback_data="cat|Бургеры"),
            types.InlineKeyboardButton("Пицца🍕",          callback_data="cat|Пицца")
        )
        markup.row(
            types.InlineKeyboardButton("Суши🍣",           callback_data="cat|Суши"),
            types.InlineKeyboardButton("Десерты🍰",        callback_data="cat|Десерты"),
            types.InlineKeyboardButton("Соусы🥫",          callback_data="cat|Соусы")
        )
        markup.row(
            types.InlineKeyboardButton("Напитки🥤",        callback_data="cat|Напитки"),
            types.InlineKeyboardButton("Завтраки🍳",       callback_data="cat|Завтраки"),
            types.InlineKeyboardButton("Супы🍲",           callback_data="cat|Супы")
        )
        bot.send_message(chat_id, "Выберите категорию блюд:", reply_markup=markup)

    # ── Выбор критерия сортировки по ресторану ────────────────────────────────
    elif data.startswith("rest|"):
        restaurant = data.split("|")[1]
        user_restaurant[user_id] = restaurant

        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("Лучшее соотношение белков/кбжу", callback_data="sort_rest|ratio"))
        markup.row(
            types.InlineKeyboardButton("Больше всего белка",   callback_data="sort_rest|protein"),
            types.InlineKeyboardButton("Меньше всего жиров",   callback_data="sort_rest|fat")
        )
        markup.row(types.InlineKeyboardButton("Меньше всего углеводов", callback_data="sort_rest|carbs"))
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="restaurant"))

        rest_display = RESTAURANT_MAP.get(restaurant, restaurant)
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text=f"🍽 Ресторан: <b>{rest_display}</b>\nВыберите критерий:",
            parse_mode="HTML",
            reply_markup=markup
        )

    # ── Выбор критерия сортировки по категории блюда ─────────────────────────
    elif data.startswith("cat|"):
        global cat_id
        category = data.split("|")[1]
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sections WHERE name = %s", (category,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            bot.send_message(chat_id, "Категория не найдена 😢")
            return
        cat_id = row[0]

        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("Лучшее соотношение белков/кбжу", callback_data="sort|ratio"))
        markup.row(
            types.InlineKeyboardButton("Больше всего белка",   callback_data="sort|protein"),
            types.InlineKeyboardButton("Меньше всего жиров",   callback_data="sort|fat")
        )
        markup.row(types.InlineKeyboardButton("Меньше всего углеводов", callback_data="sort|carbs"))
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="restaurant"))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text=f"📂 Категория: <b>{category}</b>\nВыберите критерий сортировки:",
            parse_mode="HTML",
            reply_markup=markup
        )

    # ── Топ-5 по категории ────────────────────────────────────────────────────
    elif data.startswith("sort|"):
        criterion = data.split("|")[1]
        sorted_ids = sort_by(cat_id, criterion)
        if not sorted_ids:
            bot.send_message(chat_id, "Блюд нет 😢")
            return

        conn = get_conn()
        cur = conn.cursor()
        text = "🍽 <b>Топ-5 блюд:</b>\n\n"
        for dish_id in sorted_ids:
            cur.execute(
                "SELECT dish, restaurant, kcal, protein, fat, carbs FROM dishes WHERE id = %s",
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
                f"──────────────────────\n"
            )
        cur.close()
        conn.close()
        text += "\n👉 Отправьте <b>ID блюда</b>, чтобы добавить в корзину"
        user_state[user_id] = "WAIT_DISH_ID"
        bot.send_message(chat_id, text, parse_mode="HTML")

    # ── Топ-5 по ресторану ────────────────────────────────────────────────────
    elif data.startswith("sort_rest|"):
        criterion = data.split("|")[1]
        restaurant_slug = user_restaurant.get(user_id)
        restaurant_name = RESTAURANT_MAP.get(restaurant_slug)

        if not restaurant_name:
            bot.send_message(chat_id, "❌ Неизвестный ресторан")
            return

        conn = get_conn()
        cur = conn.cursor()

        order_map = {
            "ratio":   "(protein * 4.0) / NULLIF(kcal, 0) DESC",
            "protein": "protein DESC",
            "fat":     "fat ASC",
            "carbs":   "carbs ASC",
        }
        order = order_map.get(criterion)
        if not order:
            return

        cur.execute(f"""
            SELECT id, dish, protein, fat, carbs, kcal
            FROM dishes
            WHERE restaurant = %s AND sectionid <> 9 AND sectionid <> 10
            ORDER BY {order}
            LIMIT 5
        """, (restaurant_name,))
        dishes = cur.fetchall()
        cur.close()
        conn.close()

        if not dishes:
            bot.send_message(chat_id, "❌ Блюд не найдено")
            return

        text = "🍽 <b>Топ-5 блюд:</b>\n\n"
        for i, d in enumerate(dishes, 1):
            text += (
                f"{i}. <b>{d[1]}</b>\n"
                f"Б {d[2]}г | Ж {d[3]}г | У {d[4]}г | {d[5]} ккал\n"
                f"───────\nID: <code>{d[0]}</code>\n\n"
            )
        user_state[user_id] = "WAIT_DISH_ID"
        bot.send_message(
            chat_id,
            text + "👉 Отправьте ID блюда, чтобы добавить в корзину",
            parse_mode="HTML"
        )


# ─── ТЕКСТОВЫЕ ХЕНДЛЕРЫ ───────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text.isdigit())
def add_by_id(message):
    if user_state.get(message.from_user.id) != "WAIT_DISH_ID":
        return
    result = add_to_cart_by_id(message.from_user.id, int(message.text))
    bot.send_message(message.chat.id, result)
    user_state[message.from_user.id] = None


@bot.message_handler(content_types=['text'])
def handle_text(message):
    from normalize_text import normalize_restaurant
    text = message.text

    if text in ["Додо пицца", "dodo pizza", "Dodo pizza", "Додо", "dodo", "Dodo", "додо", "пиццы", "Пиццы"]:
        ask_for_dish(message.chat.id, "Додо пицца")
    elif text in ["вендис", "Вендис", "Wendys", "wendys", "WENDYS", "wendy's", "Wendy's", "Wendy", "wendy"]:
        ask_for_dish(message.chat.id, "Wendy's")
    elif text in ["Hardee's", "hardees", "Hardes", "hardes", "Хардис", "хардис", "ХАРДИС", "харди", "хард"]:
        ask_for_dish(message.chat.id, "Hardee's")
    elif text in ["Баханди", "баханди", "БАХАНДИ", "bahandi", "Bahandi", "BAHANDI", "бахан"]:
        ask_for_dish(message.chat.id, "Баханди")
    elif text in ["кофе бум", "Кофе бум", "Кофе Бум", "КОФЕ БУМ", "coffeeboom", "coffee boom", "Coffee Boom"]:
        ask_for_dish(message.chat.id, "Кофе Бум")
    else:
        normalized = normalize_restaurant(text)
        ask_for_dish(message.chat.id, normalized)


# ─── УДАЛЕНИЕ ИЗ КОРЗИНЫ ──────────────────────────────────────────────────────

def delete_dish(message, user_id):
    conn = get_conn()
    cur = conn.cursor()

    text = message.text.strip()
    if not all(ch.isdigit() or ch.isspace() for ch in text):
        bot.send_message(message.chat.id, "❌ Нужно ввести число!")
        cur.close()
        conn.close()
        start(message)
        return

    parts = text.split()
    if len(parts) != 2:
        bot.send_message(message.chat.id, "❌ Введите номер блюда и количество ЧЕРЕЗ ПРОБЕЛ")
        cur.close()
        conn.close()
        return

    item_number, qty_to_remove = int(parts[0]), int(parts[1])

    cur.execute("""
        SELECT id, dish FROM (
            SELECT id, dish,
                   ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
            FROM cart_items WHERE user_id = %s
        ) t WHERE rn = %s
    """, (user_id, item_number))
    res1 = cur.fetchone()

    if not res1:
        bot.send_message(message.chat.id, f"❌ В корзине нет блюда №{item_number}")
        cur.close()
        conn.close()
        return

    real_id, dish_name = res1

    cur.execute(
        "SELECT weight, kcal, protein, fat, carbs FROM dishes WHERE dish = %s",
        (dish_name,)
    )
    res2 = cur.fetchone()
    weight, kcal_p, protein_p, fat_p, carbs_p = res2

    cur.execute("""
        UPDATE cart_items
        SET weight   = weight   - %s,
            quantity = quantity - %s,
            kcal     = kcal     - %s,
            protein  = protein  - %s,
            fat      = fat      - %s,
            carbs    = carbs    - %s
        WHERE id = %s AND user_id = %s
        RETURNING quantity;
    """, (
        qty_to_remove * float(weight),
        qty_to_remove,
        qty_to_remove * float(kcal_p),
        qty_to_remove * float(protein_p),
        qty_to_remove * float(fat_p),
        qty_to_remove * float(carbs_p),
        real_id, user_id
    ))
    cur.execute(
        "DELETE FROM cart_items WHERE id = %s AND user_id = %s AND quantity <= 0",
        (real_id, user_id)
    )

    conn.commit()
    cur.close()
    conn.close()
    bot.send_message(message.chat.id, f"✅ Блюдо №{item_number} удалено из корзины!")


# ─── НЕЧЁТКИЙ ПОИСК БЛЮДА ────────────────────────────────────────────────────

def dish_handling_func_1(message, restaurant):
    from rapidfuzz import process, fuzz

    dish_input = message.text.strip()
    restaurant_name = restaurant.strip()
    user_last_restaurant[message.from_user.id] = restaurant_name

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT dish FROM dishes WHERE restaurant = %s", (restaurant_name,))
    all_dishes = cur.fetchall()

    back_cb = _get_back_cb(restaurant_name)

    if not all_dishes:
        # Пробуем универсальные напитки как fallback
        cur.execute("""
            SELECT name, volume_ml, kcal, protein, fat, carbs
            FROM universal_drinks
            WHERE name ILIKE %s
        """, (f"%{dish_input}%",))
        drink = cur.fetchone()
        cur.close()
        conn.close()

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data=back_cb))

        if drink:
            name, volume, kcal, protein, fat, carbs = drink
            bot.send_message(
                message.chat.id,
                f"🥤 <b>{name}</b> {volume} мл\n"
                f"──────────────────\n"
                f"Калории: {kcal} ккал\n"
                f"Белки: {protein} г\n"
                f"Жиры: {fat} г\n"
                f"Углеводы: {carbs} г\n"
                f"──────────────────\n"
                f"ℹ️ Универсальный напиток — данные одинаковы для всех ресторанов",
                parse_mode="HTML",
                reply_markup=markup
            )
        else:
            bot.send_message(message.chat.id, "Блюда для этого ресторана не найдены.", reply_markup=markup)
        return

    dishes_names = [row[0] for row in all_dishes]
    dishes_map = {name.lower(): name for name in dishes_names}

    best_matches = process.extract(
        dish_input.lower(),
        list(dishes_map.keys()),
        scorer=fuzz.ratio,
        limit=5
    )
    best_matches = [(dishes_map[name], score, idx) for name, score, idx in best_matches]

    markup = types.InlineKeyboardMarkup()
    added = False
    exact_dish_id = None

    for name, score, _ in best_matches:
        cur.execute(
            "SELECT id FROM dishes WHERE restaurant = %s AND dish = %s",
            (restaurant_name, name)
        )
        res = cur.fetchone()
        if not res:
            continue
        if score >= 99:
            exact_dish_id = res[0]
        elif score >= 10:
            markup.add(types.InlineKeyboardButton(name, callback_data=f"dish|{res[0]}"))
            added = True

    markup.add(types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data=back_cb))

    if exact_dish_id:
        cur.execute("""
            SELECT dish, restaurant, weight, kcal, protein, fat, carbs,
                   allergenes, suspicious_kbju, suspicious_text
            FROM dishes WHERE id = %s
        """, (exact_dish_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            markup2 = types.InlineKeyboardMarkup()
            markup2.add(types.InlineKeyboardButton("🔍 Искать другое блюдо.", callback_data=back_cb))
            markup2.row(types.InlineKeyboardButton(
                "🛒 Добавить блюдо в корзину.",
                callback_data=f"add_dish_to_cart|{exact_dish_id}"
            ))
            bot.send_message(
                message.chat.id,
                format_dish_message(row),
                parse_mode='HTML',
                reply_markup=markup2
            )
            add_to_history(message.from_user.id, row[0], row[1])

    elif added:
        cur.close()
        conn.close()
        bot.send_message(message.chat.id, "Похожие блюда:", reply_markup=markup)

    else:
        # Нет совпадений в ресторане — проверяем универсальные напитки
        cur.execute("""
            SELECT name, volume_ml, kcal, protein, fat, carbs
            FROM universal_drinks
            WHERE name ILIKE %s
            LIMIT 1
        """, (f"%{dish_input}%",))
        drink = cur.fetchone()
        cur.close()
        conn.close()

        if drink:
            name, volume, kcal, protein, fat, carbs = drink
            bot.send_message(
                message.chat.id,
                f"🥤 <b>{name}</b> {volume} мл\n"
                f"──────────────────\n"
                f"Калории: {kcal} ккал\n"
                f"Белки: {protein} г\n"
                f"Жиры: {fat} г\n"
                f"Углеводы: {carbs} г\n"
                f"──────────────────\n"
                f"ℹ️ Универсальный напиток — данные одинаковы для всех ресторанов",
                parse_mode="HTML",
                reply_markup=markup
            )
        else:
            bot.send_message(
                message.chat.id,
                "Этого блюда нет в базе. Попробуйте ввести другое название или уточнить запрос.",
                reply_markup=markup
            )


# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────

bot.polling(none_stop=True)