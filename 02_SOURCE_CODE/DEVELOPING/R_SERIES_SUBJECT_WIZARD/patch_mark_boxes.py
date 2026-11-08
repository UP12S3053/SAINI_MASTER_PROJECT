import hashlib
import py_compile
from pathlib import Path

DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_data.py")
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX\school_data_before_mark_boxes.py")
APP = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BANK = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"

OLD_FN = '''def save_marks(conn, school_code, uid, subject, exam_slot, obtained):
    ensure_schema(conn)
    uid = (uid or "").strip().upper()
    subject = _subject(subject)
    slots = dict(EXAMS)
    if exam_slot not in slots:
        raise ValueError("Choose an exam")
    student = conn.execute(
        "SELECT class_name FROM school_students WHERE school_code=? AND student_uid=?",
        (school_code, uid),
    ).fetchone()
    if student is None:
        raise ValueError("Student not found for this school")
    plan = conn.execute(
        """SELECT max_marks FROM school_paper_needs
        WHERE school_code=? AND class_name=? AND subject=?""",
        (school_code, student[0], subject),
    ).fetchone()
    max_marks = plan[0] if plan else 100
    score = _number(obtained, "Marks", 0, max_marks)
    conn.execute(
        """INSERT INTO school_marks
        (school_code, student_uid, subject, exam_slot, obtained, max_marks, created_at)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(school_code, student_uid, subject, exam_slot)
        DO UPDATE SET obtained=excluded.obtained, max_marks=excluded.max_marks""",
        (school_code, uid, subject, exam_slot, score, max_marks, _now()),
    )
    conn.commit()
    return uid'''

NEW_FN = '''def save_marks(conn, school_code, uid, subject, boxes):
    ensure_schema(conn)
    uid = (uid or "").strip().upper()
    subject = _subject(subject)
    student = conn.execute(
        "SELECT class_name FROM school_students WHERE school_code=? AND student_uid=?",
        (school_code, uid),
    ).fetchone()
    if student is None:
        raise ValueError("Student not found for this school")
    filled = [str(item or "").strip() for item in boxes]
    if len(filled) != 4:
        raise ValueError("Four mark boxes are required")
    used = [item != "" for item in filled]
    if used == [True, True, True, True]:
        plan = (("M1", "First monthly"), ("HY", "Half-yearly"), ("M2", "Second monthly"), ("AN", "Annual"))
    elif used == [True, True, True, False]:
        plan = (("Q", "Quarterly"), ("HY", "Half-yearly"), ("AN", "Annual"))
    else:
        raise ValueError("Fill the first 3 boxes, or all 4. Do not leave a gap.")
    cap = conn.execute(
        """SELECT max_marks FROM school_paper_needs
        WHERE school_code=? AND class_name=? AND subject=?""",
        (school_code, student[0], subject),
    ).fetchone()
    max_marks = cap[0] if cap else 100
    saved = []
    for index, (slot, label) in enumerate(plan):
        score = _number(filled[index], label, 0, max_marks)
        conn.execute(
            """INSERT INTO school_marks
            (school_code, student_uid, subject, exam_slot, obtained, max_marks, created_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(school_code, student_uid, subject, exam_slot)
            DO UPDATE SET obtained=excluded.obtained, max_marks=excluded.max_marks""",
            (school_code, uid, subject, slot, score, max_marks, _now()),
        )
        saved.append(label)
    conn.commit()
    return uid + " (" + ", ".join(saved) + ")"'''

OLD_CALL = '''notice = "Marks saved for " + save_marks(
                        conn, school_code, form.get("student_uid"), form.get("subject"),
                        form.get("exam_slot"), form.get("obtained"),
                    )'''

NEW_CALL = '''notice = "Marks saved for " + save_marks(
                        conn, school_code, form.get("student_uid"), form.get("subject"),
                        [form.get("mark_1"), form.get("mark_2"), form.get("mark_3"), form.get("mark_4")],
                    )'''

OLD_FORM = '''+ '<label>Subject</label><input name="subject" required maxlength="20" placeholder="MATH">'
            + '<label>Exam</label><select name="exam_slot">' + exam_options + "</select>"
            + '<label>Obtained marks</label><input name="obtained" required inputmode="decimal">'
            + '<button type="submit">Save marks</button></form>'
'''

NEW_FORM = '''+ '<label>Subject</label><input name="subject" required maxlength="20" placeholder="MATH">'
            + '<p>Fill 3 boxes for Quarterly, Half-yearly, Annual. Fill all 4 for First monthly, Half-yearly, Second monthly, Annual.</p>'
            + '<label>Obtained marks 1</label><input name="mark_1" inputmode="decimal">'
            + '<label>Obtained marks 2</label><input name="mark_2" inputmode="decimal">'
            + '<label>Obtained marks 3</label><input name="mark_3" inputmode="decimal">'
            + '<label>Obtained marks 4, optional</label><input name="mark_4" inputmode="decimal">'
            + '<button type="submit">Save marks</button></form>'
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sha(ORIG) != APP or sha(DB) != BANK:
        raise SystemExit("ABORT ORIGINAL")
    text = DEV.read_text(encoding="utf-8")
    for old in (OLD_FN, OLD_CALL, OLD_FORM):
        if text.count(old) != 1:
            raise SystemExit("ABORT MATCH " + str(text.count(old)))
    updated = text.replace(OLD_FN, NEW_FN, 1).replace(OLD_CALL, NEW_CALL, 1).replace(OLD_FORM, NEW_FORM, 1)
    if "mark_4" not in updated or "exam_slot" in updated.split('elif part == "result"')[1].split("else:")[0]:
        raise SystemExit("ABORT RESULT")
    temporary = DEV.with_name(DEV.name + ".marks_tmp")
    compiled = DEV.with_name(DEV.name + ".marks_check.pyc")
    temporary.write_text(updated, encoding="utf-8", newline="\n")
    try:
        py_compile.compile(str(temporary), cfile=str(compiled), doraise=True)
    finally:
        if compiled.exists():
            compiled.unlink()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    BAK.write_bytes(DEV.read_bytes())
    DEV.write_text(updated, encoding="utf-8", newline="\n")
    temporary.unlink()
    if sha(ORIG) != APP or sha(DB) != BANK:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("boxes=4")
    print("dropdown=removed")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")


if __name__ == "__main__":
    main()
