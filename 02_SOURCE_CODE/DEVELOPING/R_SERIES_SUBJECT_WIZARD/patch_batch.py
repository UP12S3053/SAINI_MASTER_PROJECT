import hashlib, py_compile
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
MOD = DEV / "school_delivery.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
AH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
FUNC = 'def _batch_sheet(conn, order_id):\n    row = conn.execute(\n        "SELECT job_code, school_code, want_cards FROM school_delivery_orders WHERE id=?",\n        (order_id,),\n    ).fetchone()\n    if row is None:\n        raise ValueError("Job not found")\n    if not row[2]:\n        raise ValueError("This job has no ID cards")\n    school = conn.execute(\n        "SELECT school_name, city FROM school_accounts WHERE school_code=?",\n        (row[1],),\n    ).fetchone()\n    slots = conn.execute(\n        """SELECT position, student_uid, class_name, student_name\n        FROM school_delivery_slots WHERE order_id=? ORDER BY position""",\n        (order_id,),\n    ).fetchall()\n    if not slots or len(slots) % 10:\n        raise ValueError("A4 batch needs 10, 20, or 30 card positions")\n    cards = []\n    for position, uid, class_name, student_name in slots:\n        extra = conn.execute(\n            "SELECT father_name, photo_path FROM school_students WHERE school_code=? AND student_uid=?",\n            (row[1], uid),\n        ).fetchone()\n        father = extra[0] if extra else ""\n        photo = extra[1] if extra else ""\n        place = ((position - 1) % 10) + 1\n        cards.append(\n            \'<article class="card"><div class="top"><b>%s</b><span>%s</span></div>\'\n            \'<div class="mid">%s<div><b>%s</b><br>Father: %s<br>Class %s<br>%s</div></div>\'\n            \'<div class="foot">%s &nbsp; Place %d</div></article>\'\n            % (\n                _esc(school[0] if school else row[1]),\n                _esc(row[0]),\n                _face(conn, row[1], uid, photo),\n                _esc(student_name),\n                _esc(father),\n                _esc(class_name),\n                _esc(uid),\n                _esc(school[1] if school else ""),\n                place,\n            )\n        )\n    pages = []\n    total_sheets = len(cards) // 10\n    for number in range(total_sheets):\n        chunk = "".join(cards[number * 10:(number + 1) * 10])\n        pages.append(\n            \'<section class="sheet"><p class="noprint">Sheet %d of %d</p><div class="grid">%s</div></section>\'\n            % (number + 1, total_sheets, chunk)\n        )\n    return (\n        \'<!doctype html><html><head><meta charset="utf-8"><title>A4 \'\n        + _esc(row[0]) + \'</title><style>\'\n        \'@page{size:A4 portrait;margin:8mm}\'\n        \'body{font-family:Arial,sans-serif;margin:0;color:#172033}\'\n        \'.sheet{page-break-after:always}\'\n        \'.grid{display:grid;grid-template-columns:85mm 85mm;grid-auto-rows:54mm;gap:2mm}\'\n        \'.card{border:0.4mm solid #17365d;box-sizing:border-box;padding:2mm;overflow:hidden}\'\n        \'.top,.foot{display:flex;justify-content:space-between;font-size:9px}\'\n        \'.mid{display:flex;gap:2mm;margin-top:1mm;font-size:11px}\'\n        \'img.face{width:22mm;height:28mm;object-fit:cover}\'\n        \'.noprint a,button{font-size:14px}\'\n        \'@media print{.noprint{display:none}}\'\n        \'</style></head><body><p class="noprint"><a href="/saini-queue?job=\'\n        + str(order_id) + \'">Back to job</a> \'\n        \'<button type="button" onclick="window.print()">Print 2 x 5</button></p>\'\n        + "".join(pages) + \'</body></html>\'\n    )\n\n\n'
LINK_OLD = '        + \'<p class="noprint"><button type="button" onclick="window.print()">Print shop sheet</button></p>\'\n'
LINK_NEW = '        + \'<p class="noprint"><button type="button" onclick="window.print()">Print shop sheet</button> \'\n        + \'<a href="/saini-queue?sheet=\' + str(order_id) + \'">Print A4, 2 x 5</a></p>\'\n'
GATE_OLD = '    job_text = (request.args.get("job") or "").strip()\n'
GATE_NEW = '    sheet_text = (request.args.get("sheet") or "").strip()\n    if request.method == "GET" and sheet_text.isdigit():\n        try:\n            return _batch_sheet(conn, int(sheet_text))\n        except ValueError as exc:\n            error = str(exc)\n    job_text = (request.args.get("job") or "").strip()\n'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def once(text, old, new, name):
    if text.count(old) != 1:
        raise SystemExit("ABORT " + name)
    return text.replace(old, new, 1)

def main():
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL")
    raw = MOD.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "def _batch_sheet" in text or "Print A4, 2 x 5" in text:
        raise SystemExit("ABORT ALREADY")
    text = once(text, "def saini_queue(get_db, request, session):\n", FUNC + "def saini_queue(get_db, request, session):\n", "FUNC")
    text = once(text, LINK_OLD, LINK_NEW, "LINK")
    text = once(text, GATE_OLD, GATE_NEW, "GATE")
    if text.count("grid-template-columns:85mm 85mm") != 1:
        raise SystemExit("ABORT RESULT")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    tmp = MOD.with_name("school_delivery.batch_tmp")
    pyc = MOD.with_name("school_delivery.batch_tmp.pyc")
    tmp.write_bytes(text.replace("\n", newline).encode("utf-8"))
    try:
        py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
    finally:
        if pyc.exists():
            pyc.unlink()
    BAK.mkdir(parents=True, exist_ok=True)
    (BAK / "school_delivery_before_batch_sheet.py").write_bytes(raw)
    MOD.write_bytes(tmp.read_bytes())
    tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("batch=a4-2x5")
    print("school_cannot_print=yes")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()
