import sqlite3

con = sqlite3.connect("file:paper_bank.db?mode=ro", uri=True)
rows = con.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()

print("DATABASE TABLES:")
for name, sql in rows:
    print("\nTABLE:", name)
    print(sql)

con.close()
