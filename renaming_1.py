def rename(callback):
    mapping = {
        'mcdonalds': "McDonald's",
        'kfc': 'KFC',
        'burgerk': 'Burger King',
        'tanuki': 'Tanuki',
        'starbucks': 'Starbucks'
    }
    return mapping.get(callback.data, callback.data)
