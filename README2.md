# КБЖУ-бот — деплой в облако

## Необходимые переменные окружения

```
BOT_TOKEN           — токен Telegram-бота (от @BotFather)
DATABASE_URL        — строка подключения к PostgreSQL
                      (postgresql://user:pass@host:5432/dbname)
```

Опционально (только для миграции аналитики в Google Sheets):
```
GOOGLE_CREDS_JSON   — JSON сервисного аккаунта Google (строкой)
ANALYTICS_SHEET_ID  — ID Google-таблицы из URL
```

## Установка зависимостей

```bash
pip install -r requirements.txt
```

## Запуск бота

```bash
python bot.py
```

## Файлы аналитики

| Команда | Назначение |
|---------|-----------|
| `python dashboard_weekly_sqlite.py` | Еженедельный отчёт |
| `python analytics_migrate.py` | Выгрузка аналитики в Google Sheets |
| `python analytics_db_admin.py stats` | Статистика базы |
| `python analytics_db_admin.py backup` | Резервная копия |
| `python test_analytics.py` | Проверка работы аналитики |

## База данных аналитики

`analytics.db` — создаётся автоматически при первом запуске.
Хранит все события: поиски, добавления в корзину, источники трафика и т.д.
