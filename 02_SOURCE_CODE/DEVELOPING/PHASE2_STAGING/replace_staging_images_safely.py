from pathlib import Path
from PIL import Image
from datetime import datetime
import sqlite3
import shutil
import hashlib
import json
import sys

root = Path(r"D:\SAINI_PHASE2_STAGING")
src_dir = Path.home() / "Downloads"
image_dir = root / "images"
db_path = root / "paper_bank.db"

names = [f"LKG-MATH-Q{i:03}.png" for i in range(1, 67)]

# Preflight: all source images must exist and be readable.
for name in names:
    p = src_dir / name
    if not p.is_file():
        sys.exit(f"STOP: Missing source image: {p}")
    try:
        with Image.open(p) as im:
            im.verify()
    except Exception as e:
        sys.exit(f"STOP: Invalid image {name}: {e}")

if not db_path.is_file():
    sys.exit(f"STOP: Database missing: {db_path}")
if not image_dir.is_dir():
    sys.exit(f"STOP: Existing image folder missing: {image_dir}")

# Verify the expected LKG Maths records and image paths before changing anything.
con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
try:
    rows = con.execute("""
        SELECT id, image_path, content_json
        FROM questions
        WHERE id BETWEEN 7 AND 72
        ORDER BY id
    """).fetchall()

    if len(rows) != 66:
        sys.exit(f"STOP: Expected 66 records for IDs 7-72; found {len(rows)}")

    for i, row in enumerate(rows, 1):
        expected_name = f"LKG-MATH-Q{i:03}.png"
        stored = str(row["image_path"] or "")
        if Path(stored).name != expected_name:
            sys.exit(
                f"STOP: ID {row['id']} path mismatch: {stored!r}; "
                f"expected filename {expected_name}"
            )
finally:
    con.close()

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_root = root / f"BACKUP_BEFORE_IMAGE_REPLACEMENT_{stamp}"
backup_images = backup_root / "images"
backup_images.mkdir(parents=True)

# Back up database and the 66 existing images before replacement.
shutil.copy2(db_path, backup_root / "paper_bank.db")
for name in names:
    old = image_dir / name
    if not old.is_file():
        sys.exit(f"STOP: Existing staged image missing: {old}")
    shutil.copy2(old, backup_images / name)

(backup_root / "backup_manifest.json").write_text(
    json.dumps({
        "database": str(db_path),
        "source_folder": str(src_dir),
        "image_count": len(names),
        "backup_timestamp": stamp
    }, indent=2),
    encoding="utf-8"
)

# Copy new images over matching staging filenames; do not resize or transform.
for name in names:
    shutil.copy2(src_dir / name, image_dir / name)

# Verify exact dimensions and bytes after copy.
errors = []
for name in names:
    src_hash = hashlib.sha256((src_dir / name).read_bytes()).hexdigest()
    dst_hash = hashlib.sha256((image_dir / name).read_bytes()).hexdigest()
    with Image.open(src_dir / name) as a, Image.open(image_dir / name) as b:
        if a.size != b.size or src_hash != dst_hash:
            errors.append(name)

if errors:
    print("FAIL: Copy verification failed:", errors)
    print("Backup retained at:", backup_root)
    sys.exit(1)

print("SUCCESS: 66 updated images copied to staging.")
print("Database was not modified; existing question IDs and paths remain unchanged.")
print("Backup:", backup_root)
print("Original Downloads images were not modified.")
