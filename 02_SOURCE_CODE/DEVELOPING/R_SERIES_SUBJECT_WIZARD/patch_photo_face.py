import hashlib, py_compile
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
MOD = DEV / "school_delivery.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
AH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
PAIRS = [('import hmac\n', 'import base64\nimport hmac\n'), ('from datetime import datetime\n\nimport school_registry\n', 'from datetime import datetime\nfrom pathlib import Path\n\nimport school_registry\n'), ('def _job_card(conn, order_id):\n', 'def _face(conn, school_code, uid, stored):\n    if not stored:\n        return "NO"\n    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent\n    if root.name != "DEVELOPMENT_SUBJECT_WIZARD":\n        return "NO"\n    folder = (root / "school_photos" / school_code).resolve()\n    path = (folder / (str(uid) + ".jpg")).resolve()\n    if path.parent != folder or not path.is_file():\n        return "NO"\n    raw = path.read_bytes()\n    kind = "png" if raw.startswith(b"\\x89PNG") else "jpeg"\n    return (\n        \'<img class="face" alt="" src="data:image/\'\n        + kind\n        + ";base64,"\n        + base64.b64encode(raw).decode("ascii")\n        + \'">\'\n    )\n\n\ndef _card_sheet(conn, school_code):\n    rows = conn.execute(\n        """SELECT student_uid, class_name, student_name, father_name, mobile, address, photo_path\n        FROM school_students WHERE school_code=? ORDER BY class_name, student_name""",\n        (school_code,),\n    ).fetchall()\n    body = ""\n    for item in rows:\n        cells = "".join("<td>%s</td>" % _esc(cell) for cell in item[:6])\n        cells += "<td>%s</td>" % _face(conn, school_code, item[0], item[6])\n        body += "<tr>" + cells + "</tr>"\n    return _sheet("ID cards", ("UID", "Class", "Student", "Father", "Mobile", "Address", "Photo"), [])[:-8] + body + "</table>"\n\n\ndef _job_card(conn, order_id):\n'), ('        students = conn.execute(\n            """SELECT student_uid, class_name, student_name, father_name, mobile, address,\n            CASE WHEN photo_path=\'\' THEN \'NO\' ELSE \'YES\' END\n            FROM school_students WHERE school_code=? ORDER BY class_name, student_name""",\n            (row[1],),\n        ).fetchall()\n        sections += _sheet("ID cards", ("UID", "Class", "Student", "Father", "Mobile", "Address", "Photo"), students)\n', '        sections += _card_sheet(conn, row[1])\n'), ('"@media print{.noprint{display:none}}"', '"@media print{.noprint{display:none}}img.face{width:78px;height:98px;object-fit:cover;display:block}"')]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL")
    raw = MOD.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if 'img class="face"' in text:
        raise SystemExit("ABORT ALREADY")
    for old, new in PAIRS:
        if text.count(old) != 1:
            raise SystemExit("ABORT COUNT")
        text = text.replace(old, new, 1)
    if 'img class="face"' not in text or "CASE WHEN photo_path" in text:
        raise SystemExit("ABORT FACE")
    tmp = MOD.with_name("school_delivery.face_tmp")
    pyc = MOD.with_name("school_delivery.face_check.pyc")
    tmp.write_bytes(text.replace("\n", newline).encode("utf-8"))
    try:
        py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
    finally:
        if pyc.exists():
            pyc.unlink()
    BAK.mkdir(parents=True, exist_ok=True)
    (BAK / "school_delivery_before_photo.py").write_bytes(raw)
    MOD.write_bytes(tmp.read_bytes())
    tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("photo=embedded")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()
