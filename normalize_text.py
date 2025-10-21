from rapidfuzz import process

restaurants = [
    "McDonald's", "Макдональдс", "Макдак",
    "KFC", "КФС",
    "Burger King", "Бургер Кинг", "БК",
    "Tanuki", "Тануки",
    "Starbucks", "Старбакс", "Старбак",
    "POPEYES", "POPES", "Попайс"
]

canonical = {
    # McDonald's
    "mcdonald's": "McDonald's",
    "макдональдс": "McDonald's",
    "макдак": "McDonald's",
    "макдоналдс": "McDonald's",
    "макдональдз": "McDonald's",
    "macdonalds": "McDonald's",
    "макдон": "McDonald's",
    "mcdonalds": "McDonald's",

    # KFC
    "kfc": "KFC",
    "кфс": "KFC",
    "кефси": "KFC",
    "кейефси": "KFC",
    "кейэфси": "KFC",
    "kfс": "KFC",

    # Burger King
    "burger king": "Burger King",
    "бургер кинг": "Burger King",
    "бк": "Burger King",
    "бургеркинг": "Burger King",
    "burgerking": "Burger King",
    "бургеркин": "Burger King",
    "burger-king": "Burger King",

    # Tanuki
    "tanuki": "Tanuki",
    "тануки": "Tanuki",
    "танукі": "Tanuki",
    "танукии": "Tanuki",
    "тануки restaurant": "Tanuki",
    "tanuky": "Tanuki",

    # Starbucks
    "starbucks": "Starbucks",
    "старбакс": "Starbucks",
    "старбак": "Starbucks",
    "старбаккс": "Starbucks",
    "старбакз": "Starbucks",
    "старбакс кофе": "Starbucks",
    "старбаксс": "Starbucks",

    # TomYumBar
    "tomyumbar": "TomYumBar",
    "томямбар": "TomYumBar",
    "том ям бар": "TomYumBar",
    "том-ям-бар": "TomYumBar",
    "томям": "TomYumBar",
    "том ям": "TomYumBar",
    "томямбарр": "TomYumBar",
    "tomyambar": "TomYumBar",

    # Popeyes
    "popeyes": "Popeyes",
    "popeye": "Popeyes",
    "popayes": "Popeyes",
    "попайс": "Popeyes",
    "попайсс": "Popeyes",
    "попай": "Popeyes",
    "попейс": "Popeyes",
    "попес": "Popeyes",
    "попайес": "Popeyes",
    "попаес": "Popeyes",
    "popeyes chicken": "Popeyes",
    "popeyes louisiana kitchen": "Popeyes"
}



def normalize_restaurant(name: str):
    name = name.strip().lower()
    best_match, score, _ = process.extractOne(name, restaurants)

    if name in canonical:
        return canonical[name]

    if score >= 70:
        return canonical[best_match.lower()]
    return None
