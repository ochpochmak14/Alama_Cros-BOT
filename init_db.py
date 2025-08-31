import sqlite3

def init_db():
    data = [
    ("McDonald's", "Биф Тейсти", 340, 842, 44, 51, 50),
    ("McDonald's", "Дабл Гранд Чизбургер", 280, 726, 47, 42, 48),
    ("McDonald's", "Big Burger", 229, 534, 26, 27, 45),
    ("McDonald's", "Гранд Чизбургер", 200, 726, 27, 42, 47),
    ("McDonald's", "Цезарь ролл", 185, 418, 27, 17, 41),
    ("McDonald's", "Чикен Классик", 192, 536, 25, 25, 55),
    ("McDonald's", "Дабл Чизбургер", 167, 434, 25, 22, 37),
    ("McDonald's", "Чизбургер", 116, 305, 15, 13, 32),
    ("McDonald's", "Гамбургер", 106, 257, 12, 9, 31),
    ("McDonald's", "Чикен Бургер", 139, 393, 15, 21, 35),
    ("McDonald's", "Чикен Тейсти", 330, 797, 32, 42, 66),
    ("McDonald's", "Наггетсы 20 шт", 372, 770, 41, 48, 45),
    ("McDonald's", "Наггетсы 10 шт", 186, 385, 21, 24, 22),
    ("McDonald's", "Наггетсы 6 шт", 111, 231, 13, 14, 13),
    ("McDonald's", "Наггетсы 4 шт", 74, 154, 8, 9, 9),
    ("McDonald's", "Картофель по-деревенски", 165, 330, 5, 15, 44),
    ("McDonald's", "Картофель фри большой", 147, 445, 6, 22, 55),
    ("McDonald's", "Картофель фри средний", 111, 340, 4, 17, 43),
    ("McDonald's", "Морковные палочки", 80, 27, 1, 0, 6),
    ("McDonald's", "Яблочные дольки", 35, 15, 0, 0, 3),
    ("McDonald's", "Салат цезарь с курицей", 300, 449, 23, 27, 28),
    ("McDonald's", "Салат цезарь с креветками", 309, 386, 21, 23, 21),
    ("McDonald's", "Кетчуп", 25, 27, 0.7, 0, 6),
    ("McDonald's", "Соус сырный", 25, 97, 0.2, 10, 1),
    ("McDonald's", "Соус 1000 островов", 25, 78, 0.3, 8, 2),
    ("McDonald's", "Соус кисло-сладкий", 25, 49, 0.2, 0, 12),
    ("McDonald's", "Соус барбекю", 25, 48, 0.3, 0, 12),
    ("McDonald's", "Соус горчичный", 25, 45, 0.5, 3.5, 4),
    ("McDonald's", "Соус чесночный", 25, 108, 0.3, 11, 1),
    ("McDonald's", "Соус терияки", 25, 48, 0.3, 0, 12),
    ("McDonald's", "Креветки 4 шт", 80, 188, 9, 9, 17),
    ("McDonald's", "Креветки 6 шт", 108, 246, 13, 12, 22),
    ("McDonald's", "Креветки 10 шт", 180, 410, 21, 20, 36),
    ("McDonald's", "Латте Гранд", 370, 249, 9, 9, 32),
    ("McDonald's", "Латте солёный попкорн", 370, 229, 9, 8, 32),
    ("McDonald's", "Латте медовая карамель", 370, 249, 8, 9, 33),
    ("McDonald's", "Coca-Cola", 500, 210, 0, 0, 53),
    ("McDonald's", "Fanta", 500, 250, 0, 0, 63),
    ("McDonald's", "Sprite", 500, 210, 0, 0, 52),
    ("McDonald's", "Coca-Cola без сахара", 500, 0, 0, 0, 0),
    ("McDonald's", "Апельсиновый сок", 300, 134, 1, 0, 32),
    ("McDonald's", "Fuse tea манго-ананас", 500, 34, 0, 0, 8),
    ("McDonald's", "Fuse tea манго-ромашка", 500, 34, 0, 0, 8),
    ("McDonald's", "Piko апельсин", 200, 88, 0, 0, 22),
]


    conn = sqlite3.connect("alamacros.sql")
    cur = conn.cursor()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS dishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant TEXT NOT NULL,
        dish TEXT NOT NULL,
        weight INTEGER,
        kcal REAL,
        protein REAL,
        fat REAL,
        carbs REAL,
        UNIQUE(restaurant, dish)
    )
    ''')

    cur.executemany('''
    INSERT OR IGNORE INTO dishes (restaurant, dish, weight, kcal, protein, fat, carbs)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', data)

    conn.commit()
    cur.close()
    conn.close()
