**BOT SETUP**
-----------------------------------------------------------------------------------------------------------------------------------------------------------------
1.Вместо **TOKEN** подставить *API-ключ* бота <img width="257" height="50" alt="изображение" src="https://github.com/user-attachments/assets/81f53fa9-5fe8-4d3b-b5a0-fbf5fd83a015" />

2.Скачать все библиотеки из **requirements.txt**

<img width="120" height="34" alt="изображение" src="https://github.com/user-attachments/assets/2855a827-3797-4da5-959b-a432c6c905dd" />

3.Запустить команду **python main.py** через консоль


<img width="216" height="43" alt="изображение" src="https://github.com/user-attachments/assets/422ce5dd-3b7d-4979-9134-001d285e0d90" />


4.Перейти в телеграм и зайти в бота

-------------------------------------------------------------------------------------------------------------------------------------------------------------------

* POSTGRESQL SETUP 1.0

1.Скачать **PgAdmin**

2.Зарегистрировать сервер в pgAdmin и создать свою Database 

3.Далее открыть **Query Tool** <img width="105" height="90" alt="изображение" src="https://github.com/user-attachments/assets/a12621a6-91f7-429c-a114-1872ba285f4b" />
и вписать 
```
CREATE TABLE dishes (
    restaurant TEXT,
    dish_name TEXT,
    weight TEXT,
    calories TEXT,
    protein TEXT,
    fat TEXT,
    carbs TEXT,
	allergens TEXT,
    sesame TEXT,
	egg TEXT,
	soy TEXT,
	mustard TEXT,
	celery TEXT,
	fish TEXT,
	nuts TEXT,
	citrus TEXT
);
```

4.Открыть **SQL shell** И вписать
```\copy dishes FROM 'ПУТЬ К ФАЙЛУ .csv' DELIMITER ',' CSV HEADER ENCODING 'UTF8';```

5.Вернуться в **Query Tool** и вписать

```
CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    dish VARCHAR(255) NOT NULL,
    restaurant VARCHAR(255) NOT NULL,
    weight NUMERIC,
    kcal NUMERIC,
    protein NUMERIC,
    fat NUMERIC,
    carbs NUMERIC,
    quantity INT DEFAULT 1,
    allergens TEXT,
    sesame TEXT,
	egg TEXT,
	soy TEXT,
	mustard TEXT,
	celery TEXT,
	fish TEXT,
	nuts TEXT,
	citrus TEXT
    
);
```
6.Опять в **Query Tool** прописать 
```
ALTER TABLE dishes ADD COLUMN id SERIAL PRIMARY KEY;
```

7.<img width="287" height="150" alt="изображение" src="https://github.com/user-attachments/assets/f04dfb76-2891-43f7-be8a-eb324bbb6155" />

**dbname=название своей database**

**password=Свой пароль**

Остальное менять не нужно!

-----------------------------------------------------------------------------------------------------------------------------------------------------------------
**POSTGRESQL SETUP 2.0**


1.В **Query Tool** пишем
```
CREATE TABLE search_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    dish TEXT NOT NULL,
    restaurant TEXT NOT NULL,
    searched_at TIMESTAMP DEFAULT NOW()
);

```
