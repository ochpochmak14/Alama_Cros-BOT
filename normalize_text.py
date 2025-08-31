from rapidfuzz import process

restaurants = [
    "McDonald’s", "Макдональдс", "Макдак",
    "KFC", "КФС",
    "Burger King", "Бургер Кинг", "БК",
    "Tanuki", "Тануки",
    "Starbucks", "Старбакс", "Старбак"
]

canonical = {
    "mcdonald’s": "McDonald’s",
    "макдональдс": "McDonald’s",
    "макдак": "McDonald’s",
    "kfc": "KFC",
    "кфс": "KFC",
    "burger king": "Burger King",
    "бургер кинг": "Burger King",
    "бк": "Burger King",
    "tanuki": "Tanuki",
    "тануки": "Tanuki",
    "starbucks": "Starbucks",
    "старбакс": "Starbucks",
    "старбак": "Starbucks"
}

def normalize_restaurant(name: str):
    name = name.strip().lower()
    best_match, score, _ = process.extractOne(name, restaurants)
    
    if name in canonical:
        return canonical[name]
    
    if score >= 70:
        return canonical[best_match.lower()]
    return None
