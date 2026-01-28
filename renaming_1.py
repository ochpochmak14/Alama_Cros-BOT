def rename(callback):
    mapping = {
        'mcdonalds': "McDonald's",
        'kfc': 'KFC',
        'burgerk': 'Burger King',
        'tanuki': 'Tanuki',
        'starbucks': 'Starbucks',
        'tomyumbar': 'TomYumBar',
        'popeyes': "Popeyes",
        'Додо пицца': "Додо пицца",
        'Додо': "Додо пицца",
    }
    return mapping.get(callback.data, callback.data)
