import telebot
from telebot import types
import psycopg2
import os
import logging
from cachetools import TTLCache
from analytics_sqlite import log_event

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kbju_bot")

bot = telebot.TeleBot(os.getenv("BOT_TOKEN"))
DATABASE_URL = os.getenv("DATABASE_URL")

# ─── ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ────────────────────────────────────────────────────

_TTL   = 6 * 3600   # записи живут 6 часов без активности
_UMAX  = 100_000    # не более 100 000 одновременных пользователей в кэше


class _TTLSet:
    """Set-совместимая обёртка над TTLCache (add / __contains__ / discard)."""
    def __init__(self, maxsize: int, ttl: int):
        self._c = TTLCache(maxsize=maxsize, ttl=ttl)

    def __contains__(self, item):
        return item in self._c

    def add(self, item):
        self._c[item] = True

    def discard(self, item):
        self._c.pop(item, None)


user_restaurant    = TTLCache(maxsize=_UMAX, ttl=_TTL)
user_state         = TTLCache(maxsize=_UMAX, ttl=_TTL)
user_last_restaurant = TTLCache(maxsize=_UMAX, ttl=_TTL)
user_cat_id        = TTLCache(maxsize=_UMAX, ttl=_TTL)
user_greeted       = _TTLSet(maxsize=_UMAX, ttl=_TTL)
user_cart_hinted   = _TTLSet(maxsize=_UMAX, ttl=_TTL)
user_goal          = TTLCache(maxsize=_UMAX, ttl=_TTL)
user_pending_source = TTLCache(maxsize=_UMAX, ttl=_TTL)

# UTM-коды → имена источников (используются в ссылках: /start ig, /start doctor …)
UTM_SOURCE_MAP = {
    "ig":        "instagram",
    "instagram": "instagram",
    "doctor":    "doctor",
    "friend":    "friend",
    "fitness":   "fitness",
}

# ── Допустимые значения из callback_data (заполняются после RESTAURANT_MAP) ──
ALLOWED_CRITERIA = {"protein", "fat", "carbs", "kcal", "ratio"}
ALLOWED_SOURCES  = {"instagram", "doctor", "friend", "fitness", "other"}

RESTAURANT_MAP = {
    "mcdonalds":  "McDonald's",
    "bella_ciao": "Bella Ciao",
    "tanuki":     "Tanuki",
    "burgerk":    "Burger King",
    "kfc":        "KFC",
    "tomyumbar":  "TomYumBar",
    "popeyes":    "Popeyes",
    "dodo":       "Додо пицца",
    "bahandi":    "Bahandi",
    "coffeeboom": "Coffee Boom",
    "wendys":     "Wendy's",
    "hardees":    "Hardee's",
}
ALLOWED_REST_KEYS = frozenset(RESTAURANT_MAP.keys())


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

    # Плашка предупреждения — только если флаг стоит И есть текст в БД
    if suspicious_kbju and suspicious_text:
        text += (
            f"\n\n{'🚨' * 5}\n"
            f"<b>⚠️ ВНИМАНИЕ: Подозрительное КБЖУ</b>\n"
            f"{suspicious_text}\n"
            f"{'🚨' * 5}"
        )

    return text


# ─── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────

def build_main_inline_markup():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("McDonald's",  callback_data='mcdonalds'),
        types.InlineKeyboardButton("KFC",         callback_data='kfc'),
        types.InlineKeyboardButton("Popeyes",     callback_data='popeyes'),
    )
    markup.row(
        types.InlineKeyboardButton("Burger King", callback_data='burgerk'),
        types.InlineKeyboardButton("Tanuki",      callback_data='tanuki'),
        types.InlineKeyboardButton("TomYumBar",   callback_data='tomyumbar'),
    )
    markup.row(
        types.InlineKeyboardButton("Bella Ciao",  callback_data='bella_ciao'),
        types.InlineKeyboardButton("Додо пицца",  callback_data='dodo'),
        types.InlineKeyboardButton("Hardee's",    callback_data='hardees'),
    )
    markup.row(
        types.InlineKeyboardButton("Wendy's",     callback_data='wendys'),
        types.InlineKeyboardButton("Bahandi",     callback_data='bahandi'),
        types.InlineKeyboardButton("Coffee Boom", callback_data='coffeeboom'),
    )
    markup.row(
        types.InlineKeyboardButton("🎯 Подбор по цели",    callback_data='cats'),
        types.InlineKeyboardButton("🛒 Корзина",           callback_data='show_cart'),
    )
    markup.row(
        types.InlineKeyboardButton("📜 История поиска",      callback_data='history'),
        types.InlineKeyboardButton("💡 Предложить улучшение", callback_data='offers'),
    )
    return markup


def send_main_menu(chat_id):
    reply_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    reply_markup.add(
        types.KeyboardButton("📋 Меню"),
        types.KeyboardButton("🛒 Корзина")
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

    # Извлекаем UTM-параметр из /start <ref_code>
    parts = message.text.split()
    ref_code = parts[1].lower() if len(parts) > 1 else None
    if ref_code:
        user_pending_source[user_id] = UTM_SOURCE_MAP.get(ref_code, "other")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT accepted FROM user_agreements WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    is_new = not row or row[0] == 0
    cur.close()
    conn.close()

    if is_new:
        send_agreement(user_id, chat_id)
        return

    bot.clear_step_handler_by_chat_id(chat_id)

    # Приветствие — только при самом первом запуске (если ещё не показывали)
    if user_id not in user_greeted:
        user_greeted.add(user_id)
        bot.send_message(
            chat_id,
            "👋 Привет! Я помогу узнать КБЖУ любого блюда из популярных ресторанов — "
            "калории, белки, жиры и углеводы. Выбери ресторан ниже чтобы начать."
        )

    # Аналитика: существующий пользователь зашёл по UTM-ссылке
    source = user_pending_source.pop(user_id, None)
    if source:
        log_event(user_id, 'bot_start', {'is_new': False, 'source': source})

    send_main_menu(chat_id)


@bot.message_handler(func=lambda m: m.text in ["📋 Меню", "🛒 Корзина"])
def show_menu(message):
    if message.text == "🛒 Корзина":
        _send_cart(message.chat.id, message.from_user.id)
        return
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
        # Приветствие — один раз после принятия соглашения
        bot.send_message(
            chat_id,
            "👋 Привет! Я помогу узнать КБЖУ любого блюда из популярных ресторанов — "
            "калории, белки, жиры и углеводы. Выбери ресторан ниже чтобы начать."
        )
        user_greeted.add(user_id)

        # Аналитика: новый пользователь
        source = user_pending_source.pop(user_id, None)
        if source:
            # UTM известен — логируем сразу, вопрос не задаём
            log_event(user_id, 'bot_start', {'is_new': True, 'source': source})
            send_main_menu(chat_id)
        else:
            # Спрашиваем откуда узнали о боте
            _ask_source(chat_id, user_id)
    else:
        user_pending_source.pop(user_id, None)  # очищаем UTM — пользователь отказался
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

    try:
        cur.execute("""
            SELECT weight, kcal, protein, fat, carbs
            FROM dishes WHERE dish = %s AND restaurant = %s
        """, (dish_name, restaurant))
        dish = cur.fetchone()

        if not dish:
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
                INSERT INTO cart_items(user_id, dish, restaurant, quantity, weight, kcal, protein, fat, carbs)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)
            """, (user_id, dish_name, restaurant, weight, kcal, protein, fat, carbs))

        conn.commit()
        return f"✅ {dish_name} ({restaurant}) добавлен в корзину!"

    except Exception:
        conn.rollback()
        logger.exception("add_to_cart: ошибка для user %s, блюдо %r", user_id, dish_name)
        return "❌ Ошибка при добавлении блюда"
    finally:
        cur.close()
        conn.close()


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

    except Exception:
        if conn:
            conn.rollback()
        logger.exception("add_to_cart_by_id: ошибка для user %s, dish_id %s", user_id, dish_id)
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


def get_cart_count(user_id) -> int:
    """Возвращает суммарное количество позиций (единиц товара) в корзине."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM cart_items WHERE user_id = %s",
        (user_id,)
    )
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return int(count)


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


# ─── УНИВЕРСАЛЬНЫЕ НАПИТКИ ────────────────────────────────────────────────────

def fuzzy_search_drink(query: str, limit: int = 5):
    """
    Нечёткий поиск напитков.
    Использует два прохода:
    1. Точное вхождение подстроки (кола → Coca-Cola, фьюс → Fuse Tea...)
    2. Нечёткое совпадение с высоким порогом (для опечаток)
    """
    from rapidfuzz import process, fuzz

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, volume_ml, kcal, protein, fat, carbs FROM universal_drinks")
    all_drinks = cur.fetchall()
    cur.close()
    conn.close()

    if not all_drinks:
        return []

    q = query.lower().strip()
    drinks_map = {row[0].lower(): row for row in all_drinks}

    # Словарь русских алиасов → часть английского названия для поиска
    # Порядок важен — длинные фразы должны быть раньше коротких
    RU_ALIASES = {
        "кока кола": "coca cola",   # без дефиса — чаще встречается в БД
        "кока-кола": "coca cola",
        "пепси кола": "pepsi",
        "пепси": "pepsi",
        "кола": "cola",             # ловит и Coca-Cola и Pepsi Cola
        "фанта": "fanta",
        "спрайт": "sprite",
        "севен ап": "7up",
        "7 ап": "7up",
        "семь ап": "7up",
        "миринда": "mirinda",
        "швепс": "schweppes",
        "швеппс": "schweppes",
        "тоник": "schweppes",
        "ред бул": "red bull",
        "ред булл": "red bull",
        "редбул": "red bull",
        "пико апельсин": "piko",
        "пико яблоко": "piko",
        "пико томат": "piko",
        "пико": "piko",
        "темпо вишня": "tempo",
        "темпо": "tempo",
        "фьюс ти": "fuse tea",
        "фьюз ти": "fuse tea",
        "фьюс чай": "fuse tea",
        "фьюс": "fuse",
        "макси чай": "maxi",
        "макси": "maxi",
    }

    # Переводим русский запрос — проверяем все алиасы (длинные совпадения в приоритете)
    translated_q = q
    best_match_len = 0
    for ru, en in RU_ALIASES.items():
        if ru in q and len(ru) > best_match_len:
            translated_q = q.replace(ru, en)
            best_match_len = len(ru)

    # Проход 1: прямое вхождение подстроки — проверяем оригинал, перевод и без дефиса
    translated_no_hyphen = translated_q.replace('-', ' ')
    substring_results = []
    for name_lower, row in drinks_map.items():
        name_no_hyphen = name_lower.replace('-', ' ')
        if (q in name_lower or
            translated_q in name_lower or
            translated_no_hyphen in name_no_hyphen):
            substring_results.append(row)
    if substring_results:
        return substring_results[:limit]

    # Проход 2: нечёткое совпадение — пробуем оба варианта запроса
    results = []
    for search_q in set([q, translated_q]):
        matches = process.extract(
            search_q,
            list(drinks_map.keys()),
            scorer=fuzz.token_set_ratio,
            limit=limit
        )
        for matched_name, score, _ in matches:
            if score >= 70:
                row = drinks_map[matched_name]
                if row not in results:
                    results.append(row)

    return results


def _format_drink_card(name, volume, kcal, protein, fat, carbs):
    """Форматирует карточку напитка в том же стиле что и карточка блюда."""
    return (
        f"🥤 Универсальный напиток\n"
        f"Название — {name} ({volume} мл)\n"
        f"------------------\n"
        f"Калории: {kcal}\n"
        f"Белки: {protein} г\n"
        f"Жиры: {fat} г\n"
        f"Углеводы: {carbs} г\n"
        f"------------------\n"
        f"ℹ️ Данные одинаковы для всех ресторанов"
    )


def search_and_send_drink(chat_id, query: str, back_markup):
    """
    Ищет напиток и показывает результат:
    - 1 результат → сразу карточка с кнопкой «В корзину»
    - Несколько → список кнопок как с блюдами, нажимаешь — открывается карточка
    """
    results = fuzzy_search_drink(query)
    if not results:
        return False

    if len(results) == 1:
        # Одно совпадение — сразу карточка
        name, volume, kcal, protein, fat, carbs = results[0]
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton(
            "🛒 В корзину",
            callback_data=f"add_drink_to_cart|{name}"
        ))
        for row in back_markup.keyboard:
            markup.row(*row)
        bot.send_message(
            chat_id,
            _format_drink_card(name, volume, kcal, protein, fat, carbs),
            parse_mode="HTML",
            reply_markup=markup
        )
    else:
        # Несколько — список кнопок, каждая открывает карточку
        markup = types.InlineKeyboardMarkup()
        for name, volume, kcal, protein, fat, carbs in results:
            markup.add(types.InlineKeyboardButton(
                f"🥤 {name} ({volume} мл)",
                callback_data=f"drink_card|{name}"
            ))
        for row in back_markup.keyboard:
            markup.row(*row)
        bot.send_message(
            chat_id,
            "🥤 <b>Похожие напитки:</b>",
            parse_mode="HTML",
            reply_markup=markup
        )

    return True


# ─── ВВОД БЛЮДА ───────────────────────────────────────────────────────────────

def _get_back_cb(restaurant_name):
    """Возвращает callback_data для кнопки Назад — в тот же ресторан."""
    for k, v in RESTAURANT_MAP.items():
        if v == restaurant_name:
            return f"back_rest|{k}"
    return "back_1"


def ask_for_dish(chat_id, restaurant, message_id=None):
    rest_key = next((k for k, v in RESTAURANT_MAP.items() if v == restaurant), None)

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_1"))
    # Кнопки быстрого доступа с контекстом ресторана
    if rest_key:
        markup.row(
            types.InlineKeyboardButton(
                f"📋 Все блюда {restaurant}",
                callback_data=f"bmenu_rest|{rest_key}"
            )
        )
        markup.row(
            types.InlineKeyboardButton(
                f"🎯 Найти по цели в {restaurant}",
                callback_data=f"goal_rest|{rest_key}"
            )
        )

    text = (
        f"Напишите блюдо из <b>{restaurant}</b> или выберите действие ниже"
        if restaurant else "❌ Некорректный ресторан"
    )

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

def sort_by(section_id, criterion, limit=5, offset=0):
    conn = get_conn()
    cur = conn.cursor()
    if criterion == "protein":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY protein DESC LIMIT %s OFFSET %s", (section_id, limit, offset))
    elif criterion == "fat":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY fat ASC LIMIT %s OFFSET %s", (section_id, limit, offset))
    elif criterion == "carbs":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s ORDER BY carbs ASC LIMIT %s OFFSET %s", (section_id, limit, offset))
    elif criterion == "kcal":
        cur.execute("SELECT id FROM dishes WHERE sectionid = %s AND kcal > 0 ORDER BY kcal ASC LIMIT %s OFFSET %s", (section_id, limit, offset))
    elif criterion == "ratio":
        cur.execute("""
            SELECT id FROM dishes
            WHERE sectionid = %s AND kcal > 0
            ORDER BY protein * 4.0 / kcal DESC
            LIMIT %s OFFSET %s
        """, (section_id, limit, offset))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]


def _format_top_row(dish_name, restaurant_name, kcal, protein, fat, carbs, dish_id, criterion):
    """Форматирует строку топ-5 с выделением ключевого параметра по цели."""
    b = f"<b>Б: {protein} г</b>" if criterion == "protein" else f"Б: {protein} г"
    j = f"<b>Ж: {fat} г</b>"     if criterion == "fat"     else f"Ж: {fat} г"
    u = f"<b>У: {carbs} г</b>"   if criterion == "carbs"   else f"У: {carbs} г"
    k = f"<b>{kcal} ккал</b>"    if criterion in ("ratio", "kcal") else f"{kcal} ккал"

    return (
        f"<b>{dish_name}</b> ({restaurant_name})\n"
        f"{b} | {j} | {u} | {k}\n"
        f"🆔 ID: <code>{dish_id}</code>\n"
        f"──────────────────────\n"
    )


def _send_top_by_category(chat_id, user_id, criterion, offset=0):
    """Показывает топ по категории с пагинацией. offset=0 — первые 5, offset=5 — следующие 5."""
    cat_id = user_cat_id.get(user_id)
    if not cat_id:
        bot.send_message(chat_id, "❌ Сначала выберите категорию")
        return

    sorted_ids = sort_by(cat_id, criterion, limit=5, offset=offset)
    if not sorted_ids:
        bot.send_message(chat_id, "Больше блюд нет 😢")
        return

    conn = get_conn()
    cur = conn.cursor()

    goal_titles = {
        "protein": "💪 Больше белка",
        "ratio":   "⚖️ Лучшее соотношение Б/ккал",
        "kcal":    "🔥 Меньше калорий",
        "fat":     "🥑 Меньше жира",
        "carbs":   "🍞 Меньше углеводов",
    }
    page_label = f"Места {offset+1}–{offset+len(sorted_ids)}"
    text = f"🏆 <b>{goal_titles.get(criterion, criterion)} — {page_label}:</b>\n\n"
    for dish_id in sorted_ids:
        cur.execute(
            "SELECT dish, restaurant, kcal, protein, fat, carbs FROM dishes WHERE id = %s",
            (dish_id,)
        )
        row = cur.fetchone()
        if not row:
            continue
        dish_name, restaurant_name, kcal, protein, fat, carbs = row
        text += _format_top_row(dish_name, restaurant_name, kcal, protein, fat, carbs, dish_id, criterion)

    cur.close()
    conn.close()

    # Кнопки навигации
    markup = types.InlineKeyboardMarkup()
    next_offset = offset + 5
    next_ids = sort_by(cat_id, criterion, limit=1, offset=next_offset)
    if next_ids:
        markup.row(types.InlineKeyboardButton(
            f"▶️ Места {next_offset+1}–{next_offset+5}",
            callback_data=f"top_cat_page|{criterion}|{next_offset}"
        ))
    if offset > 0:
        prev_offset = max(0, offset - 5)
        markup.row(types.InlineKeyboardButton(
            f"◀️ Назад к местам {prev_offset+1}–{prev_offset+5}",
            callback_data=f"top_cat_page|{criterion}|{prev_offset}"
        ))

    text += "\n👉 Отправьте <b>ID блюда</b>, чтобы добавить в корзину"
    bot.clear_step_handler_by_chat_id(chat_id)
    user_state[user_id] = "WAIT_DISH_ID"
    if offset == 0:
        user_goal[user_id] = None
    bot.send_message(chat_id, text, parse_mode="HTML",
                     reply_markup=markup if markup.keyboard else None)


def _send_top_by_restaurant(chat_id, user_id, offset=0):
    """Показывает топ по ресторану с пагинацией."""
    criterion = user_goal.get(user_id)
    restaurant_slug = user_restaurant.get(user_id)
    restaurant_name = RESTAURANT_MAP.get(restaurant_slug)

    if not restaurant_name:
        bot.send_message(chat_id, "❌ Неизвестный ресторан")
        return
    if not criterion:
        bot.send_message(chat_id, "❌ Сначала выберите цель")
        return

    # Whitelist criterion — никакие значения из callback_data не попадают в SQL
    if criterion not in ALLOWED_CRITERIA:
        logger.warning("_send_top_by_restaurant: недопустимый criterion %r от user %s", criterion, user_id)
        bot.send_message(chat_id, "❌ Неизвестный критерий")
        return

    # Статические ORDER BY фразы — никогда не формируются из пользовательских данных
    _ORDER_SQL = {
        "ratio":   "( protein * 4.0 ) / NULLIF(kcal, 0) DESC",
        "protein": "protein DESC",
        "kcal":    "kcal ASC",
        "fat":     "fat ASC",
        "carbs":   "carbs ASC",
    }
    order_clause = _ORDER_SQL[criterion]   # ключ уже проверен выше

    conn = get_conn()
    cur = conn.cursor()
    # Используем %s для всех пользовательских параметров; order_clause — статическая строка
    base_where = (
        "WHERE restaurant = %s AND sectionid <> 9 AND sectionid <> 10 AND kcal > 0"
    )
    cur.execute(
        f"SELECT id, dish, kcal, protein, fat, carbs FROM dishes {base_where} "
        f"ORDER BY {order_clause} LIMIT 5 OFFSET %s",
        (restaurant_name, offset),
    )
    dishes = cur.fetchall()

    # Проверяем есть ли следующая страница
    cur.execute(
        f"SELECT id FROM dishes {base_where} ORDER BY {order_clause} LIMIT 1 OFFSET %s",
        (restaurant_name, offset + 5),
    )
    has_next = cur.fetchone() is not None
    cur.close()
    conn.close()

    if not dishes:
        bot.send_message(chat_id, "Больше блюд нет 😢")
        return

    goal_titles = {
        "protein": "💪 Больше белка",
        "ratio":   "⚖️ Лучшее соотношение Б/ккал",
        "kcal":    "🔥 Меньше калорий",
        "fat":     "🥑 Меньше жира",
        "carbs":   "🍞 Меньше углеводов",
    }
    page_label = f"Места {offset+1}–{offset+len(dishes)}"
    text = f"🏆 <b>{restaurant_name} — {goal_titles.get(criterion, criterion)}</b>\n<i>{page_label}</i>\n\n"
    for d in dishes:
        dish_id, dish_name, kcal, protein, fat, carbs = d
        text += _format_top_row(dish_name, restaurant_name, kcal, protein, fat, carbs, dish_id, criterion)

    # Кнопки навигации
    markup = types.InlineKeyboardMarkup()
    if has_next:
        markup.row(types.InlineKeyboardButton(
            f"▶️ Места {offset+6}–{offset+10}",
            callback_data=f"top_rest_page|{criterion}|{offset+5}"
        ))
    if offset > 0:
        prev_offset = max(0, offset - 5)
        markup.row(types.InlineKeyboardButton(
            f"◀️ Назад к местам {prev_offset+1}–{prev_offset+5}",
            callback_data=f"top_rest_page|{criterion}|{prev_offset}"
        ))

    text += "\n👉 Отправьте <b>ID блюда</b>, чтобы добавить в корзину"
    bot.clear_step_handler_by_chat_id(chat_id)
    user_state[user_id] = "WAIT_DISH_ID"
    if offset == 0:
        user_goal[user_id] = None
    bot.send_message(chat_id, text, parse_mode="HTML",
                     reply_markup=markup if markup.keyboard else None)


# ─── ПРОСМОТР МЕНЮ РЕСТОРАНА ──────────────────────────────────────────────────

# Эмодзи для секций
SECTION_EMOJI = {
    "Закуски":       "🍟",
    "Салаты":        "🥗",
    "Паста":         "🍝",
    "Горячие блюда": "🍽️",
    "Бургеры":       "🍔",
    "Пицца":         "🍕",
    "Суши":          "🍣",
    "Десерты":       "🍰",
    "Соусы":         "🥫",
    "Напитки":       "🥤",
    "Завтраки":      "🍳",
    "Супы":          "🍲",
}


def send_browse_restaurant_picker(chat_id, message_id=None):
    """Показывает список ресторанов для просмотра меню.
    Можно выбрать кнопкой или написать название текстом.
    """
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("McDonald's",  callback_data="bmenu_rest|mcdonalds"),
        types.InlineKeyboardButton("POPEYES",     callback_data="bmenu_rest|popeyes"),
        types.InlineKeyboardButton("KFC",         callback_data="bmenu_rest|kfc"),
    )
    markup.row(
        types.InlineKeyboardButton("Burger King", callback_data="bmenu_rest|burgerk"),
        types.InlineKeyboardButton("Tanuki",      callback_data="bmenu_rest|tanuki"),
        types.InlineKeyboardButton("TomYumBar",   callback_data="bmenu_rest|tomyumbar"),
    )
    markup.row(
        types.InlineKeyboardButton("Додо пицца",  callback_data="bmenu_rest|dodo"),
        types.InlineKeyboardButton("Bella Ciao",  callback_data="bmenu_rest|bella_ciao"),
    )
    markup.row(
        types.InlineKeyboardButton("Wendy's",     callback_data="bmenu_rest|wendys"),
        types.InlineKeyboardButton("Hardee's",    callback_data="bmenu_rest|hardees"),
    )
    markup.row(
        types.InlineKeyboardButton("Bahandi",     callback_data="bmenu_rest|bahandi"),
        types.InlineKeyboardButton("Coffee Boom", callback_data="bmenu_rest|coffeeboom"),
    )
    markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_1"))

    text = "📖 Выберите ресторан или напишите его название:"

    if message_id:
        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=text, reply_markup=markup
        )
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def send_browse_sections(chat_id, rest_key, message_id=None):
    """
    Показывает секции, которые реально есть у ресторана в БД.
    Плюс кнопка «Всё меню».
    """
    restaurant_name = RESTAURANT_MAP.get(rest_key, rest_key)

    conn = get_conn()
    cur = conn.cursor()
    # Берём только те секции, у которых есть блюда в этом ресторане
    cur.execute("""
        SELECT DISTINCT s.id, s.name
        FROM sections s
        JOIN dishes d ON d.sectionid = s.id
        WHERE d.restaurant = %s
        ORDER BY s.id
    """, (restaurant_name,))
    sections = cur.fetchall()
    cur.close()
    conn.close()

    if not sections:
        bot.send_message(chat_id, f"❌ Меню для {restaurant_name} пока не загружено.")
        return

    markup = types.InlineKeyboardMarkup()

    # Кнопки секций — по 2 в ряд
    row_btns = []
    for sec_id, sec_name in sections:
        emoji = SECTION_EMOJI.get(sec_name, "🍴")
        btn = types.InlineKeyboardButton(
            f"{emoji} {sec_name}",
            callback_data=f"bmenu_sec|{rest_key}|{sec_id}"
        )
        row_btns.append(btn)
        if len(row_btns) == 2:
            markup.row(*row_btns)
            row_btns = []
    if row_btns:
        markup.row(*row_btns)

    # Кнопка «Всё меню»
    markup.row(types.InlineKeyboardButton(
        "📋 Всё меню", callback_data=f"bmenu_all|{rest_key}"
    ))
    markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="browse_menu"))

    text = f"📖 <b>{restaurant_name}</b> — выберите раздел:"

    if message_id:
        bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=text, parse_mode="HTML", reply_markup=markup
        )
    else:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)


def send_browse_dishes(chat_id, restaurant_name, dishes, section_name, rest_key):
    """
    Отправляет список блюд с ID постранично (по 20 блюд в сообщении).
    Формат такой же как в топ-5 — с ID для добавления в корзину.
    """
    if not dishes:
        bot.send_message(chat_id, "😢 В этом разделе пока нет блюд.")
        return

    back_markup = types.InlineKeyboardMarkup()
    back_markup.row(types.InlineKeyboardButton(
        "⬅️ К разделам", callback_data=f"bmenu_rest|{rest_key}"
    ))
    back_markup.row(types.InlineKeyboardButton(
        "🔍 Искать блюдо", callback_data=f"back_rest|{rest_key}"
    ))

    # Разбиваем на страницы по 20 блюд чтобы не превышать лимит Telegram
    PAGE_SIZE = 20
    pages = [dishes[i:i + PAGE_SIZE] for i in range(0, len(dishes), PAGE_SIZE)]

    header = f"📖 <b>{restaurant_name}</b> — <b>{section_name}</b>\n\n"

    for page_num, page in enumerate(pages):
        text = header if page_num == 0 else f"<i>(продолжение)</i>\n\n"
        for dish_id, dish_name, kcal, protein, fat, carbs in page:
            text += (
                f"<b>{dish_name}</b>\n"
                f"Б: {protein} г | Ж: {fat} г | У: {carbs} г | {kcal} ккал\n"
                f"🆔 ID: <code>{dish_id}</code>\n"
                f"──────────────\n"
            )

        # Кнопку «назад» добавляем только к последней странице
        if page_num == len(pages) - 1:
            text += "\n👉 Отправьте <b>ID блюда</b>, чтобы добавить в корзину"
            bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=back_markup)
        else:
            bot.send_message(chat_id, text, parse_mode="HTML")


def handle_browse_menu_text_input(message):
    """Обрабатывает текстовый ввод названия ресторана в разделе просмотра меню."""
    text_lower = message.text.strip().lower()

    # Ищем ресторан по алиасам
    restaurant_name = RESTAURANT_ALIASES.get(text_lower)

    # Если не нашли по алиасам — ищем прямо по значениям RESTAURANT_MAP
    if not restaurant_name:
        for name in RESTAURANT_MAP.values():
            if text_lower in name.lower() or name.lower() in text_lower:
                restaurant_name = name
                break

    if not restaurant_name:
        bot.send_message(
            message.chat.id,
            "❌ Ресторан не найден. Попробуй написать точнее или выбери из списка.",
        )
        send_browse_restaurant_picker(message.chat.id)
        return

    # Нашли ресторан — ищем его ключ и показываем секции
    rest_key = next((k for k, v in RESTAURANT_MAP.items() if v == restaurant_name), None)
    if rest_key:
        send_browse_sections(message.chat.id, rest_key)
    else:
        bot.send_message(message.chat.id, "❌ Ошибка. Попробуй выбрать из списка.")
        send_browse_restaurant_picker(message.chat.id)


# ─── ИСТОЧНИК ТРАФИКА (АНАЛИТИКА) ─────────────────────────────────────────────

def _ask_source(chat_id, user_id):
    """Показывает новому пользователю вопрос «Как узнали о боте?»."""
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Instagram",    callback_data="src|instagram"),
        types.InlineKeyboardButton("От врача",     callback_data="src|doctor"),
    )
    markup.row(
        types.InlineKeyboardButton("От друга",     callback_data="src|friend"),
        types.InlineKeyboardButton("Фитнес/спорт", callback_data="src|fitness"),
    )
    markup.row(
        types.InlineKeyboardButton("Другое",       callback_data="src|other"),
    )
    bot.send_message(chat_id, "Как вы узнали о боте? 🤔", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("src|"))
def source_handler(call):
    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    raw_source = call.data.split("|", 1)[1]
    source = raw_source if raw_source in ALLOWED_SOURCES else "other"
    log_event(user_id, 'bot_start', {'is_new': True, 'source': source})
    send_main_menu(chat_id)


# ─── ГЛАВНЫЙ CALLBACK ХЕНДЛЕР ─────────────────────────────────────────────────

def _is_main_callback(c):
    """Фильтр для главного хендлера — исключает callbacks, у которых есть свои хендлеры."""
    d = c.data or ""
    return (
        d not in ("agree_yes", "agree_no")  # agreement_handler
        and not d.startswith("src|")         # source_handler
    )


@bot.callback_query_handler(func=_is_main_callback)
def callback_message(callback):
    bot.answer_callback_query(callback.id)
    user_id = callback.from_user.id
    data = callback.data
    chat_id = callback.message.chat.id

    # ── Защита: неизвестные callback_data тихо отбрасываем ───────────────────
    # (пользователь может прислать произвольный payload через Telegram API)

    # ── Выбор ресторана из главного меню ──────────────────────────────────────
    if data in RESTAURANT_MAP:
        restaurant_name = RESTAURANT_MAP[data]
        user_last_restaurant[user_id] = restaurant_name
        ask_for_dish(chat_id, restaurant_name)

    # ── Просмотр меню ресторана ───────────────────────────────────────────────
    elif data == "browse_menu":
        log_event(user_id, 'feature_used', {'feature': 'menu_browse'})
        user_state[user_id] = "WAIT_BROWSE_RESTAURANT"
        send_browse_restaurant_picker(chat_id, callback.message.message_id)

    elif data.startswith("bmenu_rest|"):
        rest_key = data.split("|", 1)[1]
        if rest_key not in ALLOWED_REST_KEYS:
            return
        log_event(user_id, 'restaurant_view', {
            'restaurant': RESTAURANT_MAP.get(rest_key, rest_key),
            'section': 'all',
        })
        send_browse_sections(chat_id, rest_key, callback.message.message_id)

    elif data.startswith("bmenu_sec|"):
        # bmenu_sec|rest_key|section_id
        parts = data.split("|", 2)
        if len(parts) != 3:
            return
        _, rest_key, sec_id = parts
        if rest_key not in ALLOWED_REST_KEYS:
            return
        if not sec_id.isdigit():
            return
        restaurant_name = RESTAURANT_MAP.get(rest_key, rest_key)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT name FROM sections WHERE id = %s", (sec_id,))
        sec_row = cur.fetchone()
        section_name = sec_row[0] if sec_row else "Раздел"

        cur.execute("""
            SELECT id, dish, kcal, protein, fat, carbs
            FROM dishes
            WHERE restaurant = %s AND sectionid = %s
            ORDER BY dish
        """, (restaurant_name, sec_id))
        dishes = cur.fetchall()
        cur.close()
        conn.close()

        log_event(user_id, 'restaurant_view', {
            'restaurant': restaurant_name,
            'section': section_name,
        })

        # Сбрасываем step_handler чтобы ввод числа шёл в handle_numeric_input
        bot.clear_step_handler_by_chat_id(chat_id)
        user_state[user_id] = "WAIT_DISH_ID"
        user_last_restaurant[user_id] = restaurant_name
        send_browse_dishes(chat_id, restaurant_name, dishes, section_name, rest_key)

    elif data.startswith("bmenu_all|"):
        rest_key = data.split("|", 1)[1]
        if rest_key not in ALLOWED_REST_KEYS:
            return
        restaurant_name = RESTAURANT_MAP.get(rest_key, rest_key)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.dish, d.kcal, d.protein, d.fat, d.carbs
            FROM dishes d
            JOIN sections s ON s.id = d.sectionid
            WHERE d.restaurant = %s
            ORDER BY s.id, d.dish
        """, (restaurant_name,))
        dishes = cur.fetchall()
        cur.close()
        conn.close()

        # Сбрасываем step_handler чтобы ввод числа шёл в handle_numeric_input
        bot.clear_step_handler_by_chat_id(chat_id)
        user_state[user_id] = "WAIT_DISH_ID"
        user_last_restaurant[user_id] = restaurant_name
        send_browse_dishes(chat_id, restaurant_name, dishes, "Всё меню", rest_key)

    # ── История ───────────────────────────────────────────────────────────────
    elif data == "history":
        log_event(user_id, 'feature_used', {'feature': 'history'})
        show_history(callback)

    # ── Назад в главное меню ──────────────────────────────────────────────────
    elif data == "back_1":
        user_state[user_id] = None  # сбрасываем ожидание ID чтобы цифры не уходили в корзину
        show_menu1(chat_id, user_id)

    # ── Назад в тот же ресторан (с карточки блюда → ввод блюда того же ресторана)
    elif data.startswith("back_rest|"):
        rest_key = data.split("|", 1)[1]
        if rest_key not in ALLOWED_REST_KEYS:
            user_state[user_id] = None  # сбрасываем состояние даже при невалидном ключе
            return
        restaurant_name = RESTAURANT_MAP.get(rest_key)
        if restaurant_name:
            user_last_restaurant[user_id] = restaurant_name
            user_state[user_id] = None  # сбрасываем ожидание ID
            bot.clear_step_handler_by_chat_id(chat_id)
            ask_for_dish(chat_id, restaurant_name)
        else:
            show_menu1(chat_id, user_id)

    # ── Карточка блюда ────────────────────────────────────────────────────────
    elif data.startswith("dish|"):
        _, dishes_id = data.split("|", 1)
        if not dishes_id.isdigit():
            return
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

        if row:
            restaurant_name = row[1]
            user_last_restaurant[user_id] = restaurant_name
            back_cb = _get_back_cb(restaurant_name)

            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(
                f"🔍 Ещё блюдо из {restaurant_name}",
                callback_data=back_cb
            ))
            markup.row(types.InlineKeyboardButton(
                "🛒 В корзину",
                callback_data=f"add_dish_to_cart|{dishes_id}"
            ))

            bot.send_message(chat_id, format_dish_message(row), parse_mode='HTML', reply_markup=markup)
            add_to_history(user_id, row[0], row[1])
        else:
            bot.send_message(chat_id, "Блюдо не найдено.")

    # ── Корзина ───────────────────────────────────────────────────────────────
    elif data == "show_cart":
        log_event(user_id, 'feature_used', {'feature': 'cart'})
        _send_cart(chat_id, user_id)

    elif data.startswith("add_dish_to_cart|"):
        _, dishes_id = data.split("|", 1)
        if not dishes_id.isdigit():
            return
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT dish, restaurant FROM dishes WHERE id = %s", (dishes_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            dish_name, restaurant_name = result
            msg = add_to_cart(user_id, dish_name, restaurant_name)
            cart_size = get_cart_count(user_id)
            log_event(user_id, 'cart_add', {
                'dish_id': int(dishes_id),
                'restaurant': restaurant_name,
                'cart_size': cart_size,
            })
            # Подсказка про корзину — только первый раз
            if user_id not in user_cart_hinted:
                user_cart_hinted.add(user_id)
                bot.send_message(
                    chat_id,
                    "💡 Корзина считает суммарное КБЖУ всех добавленных блюд. "
                    "Удобно если заказываешь несколько позиций."
                )
            bot.send_message(chat_id, msg)

    elif data == "del_cart":
        clear_cart(user_id)
        bot.send_message(chat_id, "✅ Ваша корзина успешно очищена!")

    elif data.startswith("drink_card|"):
        drink_name = data.split("|", 1)[1]
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, volume_ml, kcal, protein, fat, carbs FROM universal_drinks WHERE name = %s",
            (drink_name,)
        )
        drink = cur.fetchone()
        cur.close()
        conn.close()

        if drink:
            name, volume, kcal, protein, fat, carbs = drink
            # Назад — в ресторан если знаем, иначе в главное меню
            last_rest = user_last_restaurant.get(user_id)
            back_cb = _get_back_cb(last_rest) if last_rest else "back_1"

            markup = types.InlineKeyboardMarkup()
            markup.row(types.InlineKeyboardButton(
                "🛒 В корзину",
                callback_data=f"add_drink_to_cart|{name}"
            ))
            markup.row(types.InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=back_cb
            ))
            bot.send_message(
                chat_id,
                _format_drink_card(name, volume, kcal, protein, fat, carbs),
                parse_mode="HTML",
                reply_markup=markup
            )
        else:
            bot.send_message(chat_id, "❌ Напиток не найден")

    elif data.startswith("add_drink_to_cart|"):
        # Добавить универсальный напиток в корзину
        drink_name = data.split("|", 1)[1]
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, volume_ml, kcal, protein, fat, carbs FROM universal_drinks WHERE name = %s",
            (drink_name,)
        )
        drink = cur.fetchone()
        cur.close()
        conn.close()

        if not drink:
            bot.send_message(chat_id, "❌ Напиток не найден")
        else:
            name, volume, kcal, protein, fat, carbs = drink
            # Добавляем в cart_items как обычное блюдо, ресторан = "Универсальный"
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT id FROM cart_items WHERE user_id = %s AND dish = %s AND restaurant = %s",
                    (user_id, name, "Универсальный напиток")
                )
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
                    """, (volume, kcal, protein, fat, carbs, existing[0]))
                else:
                    cur.execute("""
                        INSERT INTO cart_items
                            (user_id, dish, restaurant, quantity, weight, kcal, protein, fat, carbs)
                        VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)
                    """, (user_id, name, "Универсальный напиток", volume, kcal, protein, fat, carbs))
                conn.commit()
                if user_id not in user_cart_hinted:
                    user_cart_hinted.add(user_id)
                    bot.send_message(
                        chat_id,
                        "💡 Корзина считает суммарное КБЖУ всех добавленных блюд. "
                        "Удобно если заказываешь несколько позиций."
                    )
                bot.send_message(chat_id, f"✅ {name} добавлен в корзину!")
            except Exception:
                conn.rollback()
                logger.exception("add_drink_to_cart: ошибка для user %s, напиток %r", user_id, name)
                bot.send_message(chat_id, "❌ Ошибка при добавлении напитка")
            finally:
                cur.close()
                conn.close()

    elif data == "del_dish":
        user_state[user_id] = "WAIT_DELETE"
        bot.send_message(
            chat_id,
            "✏️ Введите номер блюда и количество порций, которые хотите удалить ЧЕРЕЗ ПРОБЕЛ\n"
            "Например: <code>2 1</code> — удалить 1 порцию блюда №2",
            parse_mode="HTML"
        )

    # ── Предложения ───────────────────────────────────────────────────────────
    elif data == "offers":
        bot.send_message(chat_id, "💡 Спасибо за ваши предложения!\nПожалуйста, заполните форму по ссылке ниже 👇")
        bot.send_message(chat_id, "https://docs.google.com/forms/d/e/1FAIpQLScy2RrdUY9-B7U2kOzeXWhjXPOWre5TdfTH5kSnYpQtkfh2xg/viewform?usp=sharing&ouid=105348996454328127243")

    # ── Подбор по цели (шаг 1 — выбор цели) ─────────────────────────────────
    elif data == "cats":
        log_event(user_id, 'feature_used', {'feature': 'goal'})
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("💪 Больше белка",              callback_data="goal|protein"),
            types.InlineKeyboardButton("⚖️ Лучшее соотношение Б/ккал", callback_data="goal|ratio"),
        )
        markup.row(
            types.InlineKeyboardButton("🔥 Меньше калорий",            callback_data="goal|kcal"),
            types.InlineKeyboardButton("🥑 Меньше жира",               callback_data="goal|fat"),
        )
        markup.row(
            types.InlineKeyboardButton("🍞 Меньше углеводов",          callback_data="goal|carbs"),
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='back_1'))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text="🎯 <b>Какая цель?</b>",
            parse_mode='HTML',
            reply_markup=markup
        )

    # ── Шаг 2 — выбрана цель, выбираем где искать ────────────────────────────
    elif data.startswith("goal|"):
        criterion = data.split("|")[1]
        if criterion not in ALLOWED_CRITERIA:
            return
        user_goal[user_id] = criterion

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("🏢 По ресторану", callback_data="goal_type|restaurant"),
            types.InlineKeyboardButton("🍽️ По типу блюда", callback_data="goal_type|bludo"),
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='cats'))

        goal_labels = {
            "protein": "💪 Больше белка",
            "ratio":   "⚖️ Лучшее соотношение Б/ккал",
            "kcal":    "🔥 Меньше калорий",
            "fat":     "🥑 Меньше жира",
            "carbs":   "🍞 Меньше углеводов",
        }
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text=f"Цель: <b>{goal_labels[criterion]}</b>\n\n🔍 <b>Где искать?</b>",
            parse_mode='HTML',
            reply_markup=markup
        )

    # ── Шаг 3а — по ресторану ─────────────────────────────────────────────────
    elif data == "goal_type|restaurant":
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
            types.InlineKeyboardButton("Додо пицца",  callback_data="rest|dodo")
        )
        markup.row(
            types.InlineKeyboardButton("Wendy's",     callback_data="rest|wendys"),
            types.InlineKeyboardButton("Hardee's",    callback_data="rest|hardees")
        )
        markup.row(
            types.InlineKeyboardButton("Bahandi",     callback_data="rest|bahandi"),
            types.InlineKeyboardButton("Coffee Boom", callback_data="rest|coffeeboom")
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='cats'))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text="🏢 <b>Выберите ресторан:</b>",
            parse_mode='HTML',
            reply_markup=markup
        )

    # ── Шаг 3б — по типу блюда ────────────────────────────────────────────────
    elif data == "goal_type|bludo":
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
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data='cats'))
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=callback.message.message_id,
            text="🍽️ <b>Выберите тип блюда:</b>",
            parse_mode='HTML',
            reply_markup=markup
        )

    # ── Подбор по цели прямо из ресторана (шаг 1 — цель) ─────────────────────
    elif data.startswith("goal_rest|"):
        rest_key = data.split("|", 1)[1]
        if rest_key not in ALLOWED_REST_KEYS:
            return
        user_restaurant[user_id] = rest_key
        rest_name = RESTAURANT_MAP.get(rest_key, rest_key)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("💪 Больше белка",              callback_data="sort_rest|protein"),
            types.InlineKeyboardButton("⚖️ Лучшее соотношение Б/ккал", callback_data="sort_rest|ratio"),
        )
        markup.row(
            types.InlineKeyboardButton("🔥 Меньше калорий",            callback_data="sort_rest|kcal"),
            types.InlineKeyboardButton("🥑 Меньше жира",               callback_data="sort_rest|fat"),
        )
        markup.row(
            types.InlineKeyboardButton("🍞 Меньше углеводов",          callback_data="sort_rest|carbs"),
        )
        markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"back_rest|{rest_key}"))
        bot.send_message(
            chat_id,
            f"🎯 <b>Какая цель в {rest_name}?</b>",
            parse_mode='HTML',
            reply_markup=markup
        )

    # ── Шаг 4 — выбор критерия по категории ──────────────────────────────────
    elif data.startswith("cat|"):
        category = data.split("|")[1]
        # Разрешаем только секции, которые реально есть в БД — дополнительную
        # защиту обеспечивает параметризованный запрос "SELECT id FROM sections"
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM sections WHERE name = %s", (category,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row:
            bot.send_message(chat_id, "Категория не найдена 😢")
            return
        user_cat_id[user_id] = row[0]

        # Берём цель пользователя если уже выбрана, иначе спрашиваем
        criterion = user_goal.get(user_id)
        if criterion:
            _send_top_by_category(chat_id, user_id, criterion)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("💪 Больше белка",              callback_data="sort|protein"),
                types.InlineKeyboardButton("⚖️ Лучшее соотношение Б/ккал", callback_data="sort|ratio"),
            )
            markup.row(
                types.InlineKeyboardButton("🔥 Меньше калорий",            callback_data="sort|kcal"),
                types.InlineKeyboardButton("🥑 Меньше жира",               callback_data="sort|fat"),
            )
            markup.row(
                types.InlineKeyboardButton("🍞 Меньше углеводов",          callback_data="sort|carbs"),
            )
            markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="cats"))
            bot.send_message(
                chat_id,
                f"📂 <b>{category}</b> — какая цель?",
                parse_mode="HTML",
                reply_markup=markup
            )

    # ── Пагинация топа по категории ──────────────────────────────────────────
    elif data.startswith("top_cat_page|"):
        parts = data.split("|")
        if len(parts) != 3:
            return
        _, criterion, offset_str = parts
        if criterion not in ALLOWED_CRITERIA or not offset_str.isdigit():
            return
        offset = int(offset_str)
        user_goal[user_id] = criterion
        _send_top_by_category(chat_id, user_id, criterion, offset)

    # ── Пагинация топа по ресторану ───────────────────────────────────────────
    elif data.startswith("top_rest_page|"):
        parts = data.split("|")
        if len(parts) != 3:
            return
        _, criterion, offset_str = parts
        if criterion not in ALLOWED_CRITERIA or not offset_str.isdigit():
            return
        offset = int(offset_str)
        user_goal[user_id] = criterion
        _send_top_by_restaurant(chat_id, user_id, offset)

    # ── Топ-5 по категории ────────────────────────────────────────────────────
    elif data.startswith("sort|"):
        criterion = data.split("|")[1]
        if criterion not in ALLOWED_CRITERIA:
            return
        user_goal[user_id] = criterion
        log_event(user_id, 'goal_search', {'goal': criterion, 'restaurant': 'by_category'})
        _send_top_by_category(chat_id, user_id, criterion)

    # ── Шаг 4 — выбор ресторана для подбора по цели ──────────────────────────
    elif data.startswith("rest|"):
        restaurant = data.split("|")[1]
        if restaurant not in ALLOWED_REST_KEYS:
            return
        user_restaurant[user_id] = restaurant
        criterion = user_goal.get(user_id)

        if criterion:
            _send_top_by_restaurant(chat_id, user_id)
        else:
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("💪 Больше белка",              callback_data="sort_rest|protein"),
                types.InlineKeyboardButton("⚖️ Лучшее соотношение Б/ккал", callback_data="sort_rest|ratio"),
            )
            markup.row(
                types.InlineKeyboardButton("🔥 Меньше калорий",            callback_data="sort_rest|kcal"),
                types.InlineKeyboardButton("🥑 Меньше жира",               callback_data="sort_rest|fat"),
            )
            markup.row(
                types.InlineKeyboardButton("🍞 Меньше углеводов",          callback_data="sort_rest|carbs"),
            )
            markup.row(types.InlineKeyboardButton("⬅️ Назад", callback_data="goal_type|restaurant"))
            rest_display = RESTAURANT_MAP.get(restaurant, restaurant)
            bot.send_message(
                chat_id,
                f"🏢 <b>{rest_display}</b> — какая цель?",
                parse_mode="HTML",
                reply_markup=markup
            )

    # ── Топ-5 по ресторану ────────────────────────────────────────────────────
    elif data.startswith("sort_rest|"):
        criterion = data.split("|")[1]
        if criterion not in ALLOWED_CRITERIA:
            return
        user_goal[user_id] = criterion
        restaurant_slug = user_restaurant.get(user_id)
        rest_name_for_log = RESTAURANT_MAP.get(restaurant_slug, restaurant_slug or 'unknown')
        log_event(user_id, 'goal_search', {'goal': criterion, 'restaurant': rest_name_for_log})
        _send_top_by_restaurant(chat_id, user_id)


# ─── МАППИНГ РЕСТОРАНОВ ПО НИЖНЕМУ РЕГИСТРУ ──────────────────────────────────
# Ключи — всё в нижнем регистре, значения — точное название как в БД
RESTAURANT_ALIASES = {
    # McDonald's
    "mcdonald's": "McDonald's", "mcdonalds": "McDonald's", "мак": "McDonald's",
    "макдак": "McDonald's", "макдональдс": "McDonald's", "макдоналдс": "McDonald's",
    "мaкдоналдс": "McDonald's",
    # KFC
    "kfc": "KFC", "кфс": "KFC", "кfc": "KFC",
    # Burger King
    "burger king": "Burger King", "burgerk": "Burger King", "бургер кинг": "Burger King",
    "бк": "Burger King", "бургер": "Burger King",
    # Tanuki
    "tanuki": "Tanuki", "тануки": "Tanuki",
    # TomYumBar
    "tomyumbar": "TomYumBar", "tom yum bar": "TomYumBar", "том ям бар": "TomYumBar",
    "томюмбар": "TomYumBar", "том юм": "TomYumBar",
    # Popeyes
    "popeyes": "Popeyes", "попайс": "Popeyes", "попис": "Popeyes", "popeye": "Popeyes",
    # Bella Ciao
    "bella ciao": "Bella Ciao", "белла чао": "Bella Ciao", "bellaciao": "Bella Ciao",
    # Додо пицца
    "додо пицца": "Додо пицца", "dodo pizza": "Додо пицца", "додо": "Додо пицца",
    "dodo": "Додо пицца", "пиццы": "Додо пицца",
    # Wendy's
    "wendy's": "Wendy's", "wendys": "Wendy's", "вендис": "Wendy's", "венди": "Wendy's",
    # Hardee's
    "hardee's": "Hardee's", "hardees": "Hardee's", "хардис": "Hardee's",
    "харди": "Hardee's", "хард": "Hardee's",
    # Bahandi
    "bahandi": "Bahandi", "баханди": "Bahandi", "бахан": "Bahandi",
    # Coffee Boom
    "coffee boom": "Coffee Boom", "coffeeboom": "Coffee Boom", "кофе бум": "Coffee Boom",
    "кофебум": "Coffee Boom",
}


# ─── ТЕКСТОВЫЕ ХЕНДЛЕРЫ ───────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: m.text is not None and all(c.isdigit() or c.isspace() for c in m.text.strip()) and m.text.strip())
def handle_numeric_input(message):
    user_id = message.from_user.id
    state = user_state.get(user_id)
    text = message.text.strip()

    # ── Ожидаем ID блюда для добавления в корзину ─────────────────────────────
    if state == "WAIT_DISH_ID":
        if not text.isdigit():
            bot.send_message(message.chat.id, "❌ Введите один ID блюда (одно число)")
            return
        result = add_to_cart_by_id(user_id, int(text))
        bot.send_message(message.chat.id, result)
        user_state[user_id] = None

    # ── Ожидаем номер блюда и количество для удаления из корзины ──────────────
    elif state == "WAIT_DELETE":
        parts = text.split()
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            bot.send_message(
                message.chat.id,
                "❌ Введите номер блюда и количество ЧЕРЕЗ ПРОБЕЛ\nНапример: <code>2 1</code>",
                parse_mode="HTML"
            )
            return
        user_state[user_id] = None
        delete_dish(message, user_id)

    # ── Число введено без контекста ────────────────────────────────────────────
    else:
        bot.send_message(
            message.chat.id,
            "ℹ️ Чтобы добавить блюдо по ID — сначала откройте меню ресторана или раздел «Подбор по цели»."
        )


@bot.message_handler(content_types=['text'])
def handle_text(message):
    from normalize_text import normalize_restaurant

    user_id = message.from_user.id
    text_lower = message.text.strip().lower()

    # Если ждём ввод ресторана для просмотра меню
    if user_state.get(user_id) == "WAIT_BROWSE_RESTAURANT":
        user_state[user_id] = None
        handle_browse_menu_text_input(message)
        return

    # Триггер для просмотра меню ресторана — текстом
    if text_lower in ["меню", "посмотреть меню", "меню ресторана", "просмотреть меню"]:
        user_state[user_id] = "WAIT_BROWSE_RESTAURANT"
        send_browse_restaurant_picker(message.chat.id)
        return

    # Сначала проверяем по словарю алиасов (регистронезависимо)
    if text_lower in RESTAURANT_ALIASES:
        restaurant_name = RESTAURANT_ALIASES[text_lower]
        ask_for_dish(message.chat.id, restaurant_name)
        return

    # Затем пробуем normalize_restaurant
    normalized = normalize_restaurant(message.text)
    if normalized in RESTAURANT_MAP.values():
        ask_for_dish(message.chat.id, normalized)
        return

    # Не похоже на ресторан — подсказываем
    bot.send_message(
        message.chat.id,
        "🤔 Не могу распознать ресторан. Выберите из списка или введите название точнее.",
    )
    send_main_menu(message.chat.id)


# ─── УДАЛЕНИЕ ИЗ КОРЗИНЫ ──────────────────────────────────────────────────────

def delete_dish(message, user_id):
    """Удаляет блюдо из корзины. Вызывается из handle_numeric_input после валидации."""
    # Повторная проверка входных данных (функция может вызываться из разных мест)
    try:
        parts = message.text.strip().split()
        item_number = int(parts[0])
        qty_to_remove = int(parts[1])
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, "❌ Некорректный ввод")
        return

    if qty_to_remove < 1:
        bot.send_message(message.chat.id, "❌ Количество должно быть минимум 1")
        return

    conn = None
    cur = None
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, dish, restaurant FROM (
                SELECT id, dish, restaurant,
                       ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn
                FROM cart_items WHERE user_id = %s
            ) t WHERE rn = %s
        """, (user_id, item_number))
        res1 = cur.fetchone()

        if not res1:
            bot.send_message(message.chat.id, f"❌ В корзине нет блюда №{item_number}")
            return

        real_id, dish_name, restaurant_name = res1

        # Ищем КБЖУ — блюдо могло быть удалено из основной таблицы
        cur.execute(
            "SELECT weight, kcal, protein, fat, carbs "
            "FROM dishes WHERE dish = %s AND restaurant = %s LIMIT 1",
            (dish_name, restaurant_name),
        )
        res2 = cur.fetchone()

        if not res2:
            # Блюдо удалено из БД — удаляем строку корзины целиком
            cur.execute(
                "DELETE FROM cart_items WHERE id = %s AND user_id = %s",
                (real_id, user_id),
            )
            conn.commit()
            bot.send_message(message.chat.id, f"✅ Блюдо №{item_number} удалено из корзины!")
            return

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
            real_id, user_id,
        ))
        cur.execute(
            "DELETE FROM cart_items WHERE id = %s AND user_id = %s AND quantity <= 0",
            (real_id, user_id),
        )
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Блюдо №{item_number} удалено из корзины!")

    except Exception:
        logger.exception("delete_dish: ошибка для user %s, item %s", user_id, item_number)
        if conn:
            conn.rollback()
        bot.send_message(message.chat.id, "❌ Ошибка при удалении блюда")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


# ─── НЕЧЁТКИЙ ПОИСК БЛЮДА ────────────────────────────────────────────────────

def dish_handling_func_1(message, restaurant):
    from rapidfuzz import process, fuzz

    dish_input = message.text.strip()

    # Если пользователь нажал системную кнопку — выполняем её функцию, не ищем блюдо
    if dish_input == "📋 Меню":
        bot.clear_step_handler_by_chat_id(message.chat.id)
        send_main_menu(message.chat.id)
        return
    if dish_input == "🛒 Корзина":
        bot.clear_step_handler_by_chat_id(message.chat.id)
        _send_cart(message.chat.id, message.from_user.id)
        return

    restaurant_name = restaurant.strip()
    user_last_restaurant[message.from_user.id] = restaurant_name

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT dish FROM dishes WHERE restaurant = %s", (restaurant_name,))
    all_dishes = cur.fetchall()

    back_cb = _get_back_cb(restaurant_name)

    if not all_dishes:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            f"🔍 Ещё блюдо из {restaurant_name}",
            callback_data=back_cb
        ))

        found = search_and_send_drink(message.chat.id, dish_input, markup)
        if not found:
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
        elif score >= 40:   # порог 40 — реальное сходство, не любой мусор
            markup.add(types.InlineKeyboardButton(name, callback_data=f"dish|{res[0]}"))
            added = True

    markup.add(types.InlineKeyboardButton(
        f"🔍 Ещё блюдо из {restaurant_name}",
        callback_data=back_cb
    ))

    # Параллельно ищем в универсальных напитках — всегда, независимо от результата блюд
    drink_results = fuzzy_search_drink(dish_input)

    # ── Аналитика поиска ──────────────────────────────────────────────────────
    results_count = (
        1 if exact_dish_id
        else sum(1 for _, score, _ in best_matches if score >= 40) if added
        else len(drink_results)
    )
    log_event(message.from_user.id, 'search_dish', {
        'query': dish_input,
        'restaurant': restaurant_name,
        'results_count': results_count,
    })
    if results_count == 0:
        log_event(message.from_user.id, 'zero_results', {
            'query': dish_input,
            'restaurant': restaurant_name,
        })
    # ─────────────────────────────────────────────────────────────────────────

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
            markup2.add(types.InlineKeyboardButton(
                f"🔍 Ещё блюдо из {restaurant_name}",
                callback_data=back_cb
            ))
            markup2.row(types.InlineKeyboardButton(
                "🛒 В корзину",
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
        # Если ещё нашлись напитки — показываем их тоже
        if drink_results:
            drink_markup = types.InlineKeyboardMarkup()
            search_and_send_drink(message.chat.id, dish_input, drink_markup)

    elif drink_results:
        cur.close()
        conn.close()
        drink_markup = types.InlineKeyboardMarkup()
        drink_markup.add(types.InlineKeyboardButton(
            f"🔍 Ещё блюдо из {restaurant_name}",
            callback_data=back_cb
        ))
        search_and_send_drink(message.chat.id, dish_input, drink_markup)

    else:
        cur.close()
        conn.close()
        bot.send_message(
            message.chat.id,
            "Этого блюда нет в базе. Попробуйте ввести другое название или уточнить запрос.",
            reply_markup=markup
        )

    # Если нашли точное блюдо И напитки — показываем напитки отдельным сообщением
    if exact_dish_id and drink_results:
        drink_markup = types.InlineKeyboardMarkup()
        text = "🥤 <b>Также нашли в универсальных напитках:</b>\n\n"
        for name, volume, kcal, protein, fat, carbs in drink_results:
            text += (
                f"<b>{name}</b> {volume} мл\n"
                f"Калории: {kcal} ккал | Б: {protein} г | Ж: {fat} г | У: {carbs} г\n"
                f"─────────────\n"
            )
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=drink_markup)


# ─── ЗАПУСК ───────────────────────────────────────────────────────────────────

def _polling_exception_handler(exc):
    """Логирует все необработанные исключения во время polling вместо тихого проглатывания."""
    logger.exception("Необработанное исключение в polling: %s", exc)


# error_handler — корректный параметр pyTelegramBotAPI для перехвата ошибок в polling
bot.polling(none_stop=True, error_handler=_polling_exception_handler)