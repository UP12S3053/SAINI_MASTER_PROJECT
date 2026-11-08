import sqlite3

con = sqlite3.connect("file:paper_bank.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("ALL EXISTING QUESTIONS:")
for row in con.execute("""
    SELECT id, board_id, class_level, subject, topic,
           question_type, content_json, image_path
    FROM questions
    ORDER BY id
"""):
    print(dict(row))

print("\nEXISTING PATTERNS:")
for row in con.execute("""
    SELECT id, board_id, class_level, subject, pattern_name
    FROM patterns
    ORDER BY id
"""):
    print(dict(row))

con.close()
