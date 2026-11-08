import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

orig = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
dev = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\paper_bank.db")
img = Path(r"D:\SAINI_TEACHER_TRIAL\images")
expected = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if sha256(orig) != expected:
        raise SystemExit("ABORT ORIGINAL " + sha256(orig))
    names = sorted(
        path.name
        for path in img.iterdir()
        if path.is_file()
        and path.name.startswith("UKG-MATH-Q")
        and path.suffix.lower() == ".png"
    )
    if not names:
        raise SystemExit("ABORT NO_FILES")
    con = sqlite3.connect(dev)
    con.row_factory = sqlite3.Row
    have = {
        row[0]
        for row in con.execute(
            "SELECT image_path FROM questions WHERE image_path LIKE ?",
            ("images/UKG-MATH-%",),
        )
    }
    pending = [name for name in names if "images/" + name not in have]
    print("FILES", len(names))
    print("ALREADY", len(names) - len(pending))
    print("PENDING", len(pending))
    if not pending:
        print("NOTHING_TO_ADD")
        return
    now = datetime.now()
    stamp = "{0:04d}{1:02d}{2:02d}_{3:02d}{4:02d}{5:02d}".format(
        now.year, now.month, now.day, now.hour, now.minute, now.second
    )
    backup = dev.parent / "backups" / (
        "paper_bank_before_ukg_math_bulk_" + stamp + ".db"
    )
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(dev, backup)
    created = "{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}:{5:02d}".format(
        now.year, now.month, now.day, now.hour, now.minute, now.second
    )
    added = 0
    con.execute("BEGIN")
    try:
        for name in pending:
            payload = json.dumps(
                {"stem": name, "image": name, "options": []},
                ensure_ascii=False,
            )
            digest = sha256(img / name)
            con.execute(
                "INSERT INTO questions (board_id,class_level,subject,topic,question_type,content_json,marks,image_path,created_at,immutable_hash) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    1,
                    "UKG",
                    "MATH",
                    "Worksheet",
                    "image",
                    payload,
                    1.0,
                    "images/" + name,
                    created,
                    "image-sha256:" + digest,
                ),
            )
            added += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    print("ADDED", added)
    print("BACKUP", backup)
    print("TOTAL", con.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    print(
        "LKG",
        con.execute(
            "SELECT COUNT(*) FROM questions WHERE class_level=?", ("LKG",)
        ).fetchone()[0],
    )
    print(
        "UKG_MATH",
        con.execute(
            "SELECT COUNT(*) FROM questions WHERE class_level=? AND subject=?",
            ("UKG", "MATH"),
        ).fetchone()[0],
    )
    for row in con.execute(
        "SELECT subject_code, status, activated FROM subject_enrollments"
    ):
        print("ENROLL", row["subject_code"], row["status"], row["activated"])
    print("ORIGINAL", sha256(orig))
    if sha256(orig) != expected:
        raise SystemExit("ABORT ORIGINAL_CHANGED")


if __name__ == "__main__":
    main()
