import psycopg2

conn = psycopg2.connect(
    dbname="alamacros",
    user="postgres",
    password="password_ne_nastoaychiy",
    host="127.0.0.1",
)
cursor = conn.cursor()