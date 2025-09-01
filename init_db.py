import sqlite3
import pandas as pd


def init_db():
    conn = sqlite3.connect("alamacros.db")
    cur = conn.cursor()

    cur.execute("""
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
    """)

    file1 = pd.read_csv("alamacros1.csv")

    file1 = file1.rename(columns={
        "Restaurant": "restaurant",
        "Dish Name": "dish",
        "Portion Size(g/ml)": "weight",
        "Calories": "kcal",
        "Protein(g)": "protein",
        "Fat(g)": "fat",
        "Carbs(g)": "carbs"
    })

    cur.execute("DELETE FROM dishes")

    file1.to_sql("dishes", conn, if_exists="append", index=False)

    conn.commit()
    cur.close()
    conn.close()
