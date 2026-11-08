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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sha256(orig) != expected:
        raise SystemExit("ABORT ORIGINAL " + sha256(orig))
    names = ["UKG-MATH-Q00" + str(number) + ".png" for number in range(1, 6)]
    for name in names:
        if not (img / name).is_file():
            raise SystemExit("ABORT MISSING " + name)
    con = sqlite3.connect(dev)
    con.row_factory = sqlite3.Row
    sample = con.execute(
        "SELECT content_json FROM questions WHERE image_path=?",
        ("images/LKG-MATH-Q001.png",),
    ).fetchone()
    obj = json.loads(sample["content_json"])
    print("IMAGE_FIELD", obj.get("image"))
    print("OPTIONS_LEN", len(obj.get("options") or []))
    if not isinstance(obj.get("image"), str) or "LKG-MATH-Q001" not in obj["image"]:
        raise SystemExit("ABORT IMAGE_FIELD")
    if obj.get("options") != []:
        raise SystemExit("ABORT OPTIONS")
    already = con.execute(
        "SELECT COUNT(*) FROM questions WHERE image_path LIKE ?",
        ("images/UKG-MATH-%",),
    ).fetchone()[0]
    if already:
        raise SystemExit("ABORT ALREADY " + str(already))
    now = datetime.now()
    stamp = "{0:04d}{1:02d}{2:02d}_{3:02d}{4:02d}{5:02d}".format(
        now.year, now.month, now.day, now.hour, now.minute, now.second
    )
    backup = dev.parent / "backups" / (
        "paper_bank_before_ukg_math_questions_" + stamp + ".db"
    )
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(dev, backup)
    created = "{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}:{5:02d}".format(
        now.year, now.month, now.day, now.hour, now.minute, now.second
    )
    con.execute("BEGIN")
    try:
        for name in names:
            image_value = obj["image"].replace("LKG-MATH-Q001.png", name).replace(
                "LKG-MATH-Q001", name[:-4]
            )
            if "LKG" in image_value:
                raise SystemExit("ABORT STILL_LKG " + image_value)
            payload = json.dumps(
                {"stem": name, "image": image_value, "options": []},
                ensure_ascii=False,
            )
            digest = hashlib.sha256((img / name).read_bytes()).hexdigest()
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
        con.commit()
    except Exception:
        con.rollback()
        raise
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
        "SELECT id, image_path FROM questions WHERE class_level=? AND subject=? ORDER BY id",
        ("UKG", "MATH"),
    ):
        print("ROW", row["id"], row["image_path"])
    for row in con.execute(
        "SELECT subject_code, status, activated FROM subject_enrollments"
    ):
        print("ENROLL", row["subject_code"], row["status"], row["activated"])
    print("ORIGINAL", sha256(orig))
    if sha256(orig) != expected:
        raise SystemExit("ABORT ORIGINAL_CHANGED")


if __name__ == "__main__":
    main()
