def rename(callback):
    mapping = {
        'mcdonalds': "McDonald's",
        'kfc': 'KFC',
        'burgerk': 'Burger King',
        'tanuki': 'Tanuki',
        'starbucks': 'Starbucks',
        'tomyumbar': 'TomYumBar'
    }
    return mapping.get(callback.data, callback.data)
