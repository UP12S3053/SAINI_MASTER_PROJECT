import sqlite3

con = sqlite3.connect("file:paper_bank.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("QUESTION COUNT:")
print(con.execute("SELECT COUNT(*) FROM questions").fetchone()[0])

print("\nEXISTING LKG MATH QUESTIONS:")
rows = con.execute("""
    SELECT id, board_id, class_level, subject, topic,
           question_type, content_json, image_path, immutable_hash
    FROM questions
    WHERE UPPER(class_level) = 'LKG'
      AND UPPER(subject) LIKE '%MATH%'
    LIMIT 10
""").fetchall()

for row in rows:
    print(dict(row))

print("\nBOARDS:")
for row in con.execute("SELECT id, code, name FROM boards"):
    print(dict(row))

con.close()
