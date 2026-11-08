import sqlite3
from pathlib import Path

db = Path("paper_bank.db").resolve()
print("DATABASE:", db)
print("EXISTS:", db.is_file())

if not db.is_file():
    raise SystemExit("STOP: Database file not found.")

conn = sqlite3.connect(str(db))
conn.row_factory = sqlite3.Row

try:
    tables = [
        r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
    ]
    print("\nTABLES:", tables)

    columns = [
        r["name"] for r in conn.execute("PRAGMA table_info(questions)")
    ]
    print("QUESTION COLUMNS:", columns)

    rows = conn.execute("""
        SELECT id, class_level, subject, image_path, content_json
        FROM questions
        WHERE UPPER(class_level) = 'LKG'
          AND UPPER(subject) = 'MATH'
        ORDER BY id
    """).fetchall()

    print("\nLKG MATH RECORDS:", len(rows))
    for row in rows:
        print(dict(row))
finally:
    conn.close()
