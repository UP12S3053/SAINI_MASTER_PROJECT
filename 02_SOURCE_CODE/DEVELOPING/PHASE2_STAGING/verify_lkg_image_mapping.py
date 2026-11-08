from pathlib import Path
from PIL import Image
import sqlite3
import hashlib
import json

root = Path(r"D:\SAINI_PHASE2_STAGING")
db = root / "paper_bank.db"
image_dir = root / "images"

con = sqlite3.connect(str(db))
con.row_factory = sqlite3.Row

try:
    rows = con.execute("""
        SELECT id, class_level, subject, image_path, content_json
        FROM questions
        WHERE id BETWEEN 7 AND 72
        ORDER BY id
    """).fetchall()

    print("DATABASE:", db)
    print("QUESTION RECORDS:", len(rows))

    errors = []
    for i, row in enumerate(rows, 1):
        expected = f"LKG-MATH-Q{i:03}.png"
        path_text = row["image_path"] or ""

        try:
            content = json.loads(row["content_json"] or "{}")
        except Exception:
            content = {}

        stored_name = Path(path_text).name
        image_path = image_dir / expected

        if row["class_level"] != "LKG" or row["subject"] != "MATH":
            errors.append(f"ID {row['id']}: class/subject mismatch")

        if stored_name != expected:
            errors.append(f"ID {row['id']}: path mismatch: {path_text}")

        if not image_path.is_file():
            errors.append(f"ID {row['id']}: image missing: {expected}")
            continue

        try:
            with Image.open(image_path) as im:
                dimensions = im.size
                im.verify()
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            print(
                f"ID {row['id']:>3} | {expected} | "
                f"{dimensions[0]}x{dimensions[1]} | SHA256 {digest[:16]}"
            )
        except Exception as e:
            errors.append(f"{expected}: invalid image: {e}")

    print("\nERROR COUNT:", len(errors))
    for error in errors:
        print("ERROR:", error)

    print("RESULT:", "PASS" if len(rows) == 66 and not errors else "CHECK REQUIRED")
finally:
    con.close()
