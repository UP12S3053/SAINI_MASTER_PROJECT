import hashlib, py_compile
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
APP = DEV / "app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py"
DATA = DEV / "school_data.py"
MOD = DEV / "school_delivery.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
AH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
LINK = '<a href="/admin/subjects">Subject Enrollment Wizard (DEVELOPMENT)</a>'
MODULE = 'import hmac\nimport secrets\nfrom datetime import datetime\n\nimport school_registry\n\ndef _now():\n    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")\n\n\ndef _esc(value):\n    text = str(value)\n    return (\n        text.replace("&", "&" + "amp;")\n        .replace("<", "&" + "lt;")\n        .replace(">", "&" + "gt;")\n        .replace(\'"\', "&" + "quot;")\n    )\n\n\ndef ensure_orders(conn):\n    school_registry.assert_development_db(conn)\n    conn.execute(\n        """CREATE TABLE IF NOT EXISTS school_delivery_orders (\n        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL,\n        want_cards INTEGER NOT NULL, want_marksheets INTEGER NOT NULL,\n        want_papers INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"""\n    )\n    conn.commit()\n\n\ndef save_order(conn, school_code, cards, sheets, papers):\n    ensure_orders(conn)\n    flags = (1 if cards else 0, 1 if sheets else 0, 1 if papers else 0)\n    if sum(flags) == 0:\n        raise ValueError("Choose ID cards, marksheets, or exam papers")\n    row = conn.execute(\n        "SELECT status, activated FROM school_accounts WHERE school_code=?",\n        (school_code,),\n    ).fetchone()\n    if row is None or row[1] != 0 or row[0] != "DRAFT":\n        raise ValueError("Only a DRAFT school can send a request")\n    conn.execute(\n        """INSERT INTO school_delivery_orders\n        (school_code, want_cards, want_marksheets, want_papers, status, created_at)\n        VALUES (?,?,?,?,\'REQUESTED\',?)""",\n        (school_code, flags[0], flags[1], flags[2], _now()),\n    )\n    conn.commit()\n    return school_code\n\n\ndef mark_dispatched(conn, order_id):\n    ensure_orders(conn)\n    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    changed = conn.execute(\n        """UPDATE school_delivery_orders SET status=\'DISPATCHED\'\n        WHERE id=? AND status=\'REQUESTED\'""",\n        (order_id,),\n    ).rowcount\n    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    if changed != 1 or before != after:\n        conn.rollback()\n        raise ValueError("Order is not open")\n    conn.commit()\n    return order_id\n\n\ndef orders_table(conn, school_code):\n    ensure_orders(conn)\n    rows = conn.execute(\n        """SELECT want_cards, want_marksheets, want_papers, status, created_at\n        FROM school_delivery_orders WHERE school_code=? ORDER BY id DESC""",\n        (school_code,),\n    ).fetchall()\n    body = "".join(\n        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"\n        % ("YES" if row[0] else "NO", "YES" if row[1] else "NO", "YES" if row[2] else "NO", _esc(row[3]), _esc(row[4]))\n        for row in rows\n    )\n    return (\n        "<h2>Requests sent</h2><table><tr><th>ID cards</th><th>Marksheets</th><th>Papers</th><th>Status</th><th>Time</th></tr>"\n        + body + "</table>"\n    )\n\n\ndef saini_queue(get_db, request, session):\n    conn = get_db()\n    ensure_orders(conn)\n    error = ""\n    notice = ""\n    token = session.get("saini_queue_csrf") or secrets.token_hex(16)\n    session["saini_queue_csrf"] = token\n    if request.method == "POST":\n        posted = request.form.get("csrf_token", "")\n        if not posted or not hmac.compare_digest(posted, token):\n            error = "Security token expired. Reload the page."\n        else:\n            try:\n                notice = "Dispatched order " + str(mark_dispatched(conn, int(request.form.get("order_id", "0"))))\n            except ValueError:\n                error = "Order is not open"\n        session["saini_queue_csrf"] = secrets.token_hex(16)\n        token = session["saini_queue_csrf"]\n    rows = conn.execute(\n        """SELECT id, school_code, want_cards, want_marksheets, want_papers, status, created_at\n        FROM school_delivery_orders ORDER BY id DESC"""\n    ).fetchall()\n    body = "".join(\n        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"\n        % (row[0], _esc(row[1]), "YES" if row[2] else "NO", "YES" if row[3] else "NO", "YES" if row[4] else "NO", _esc(row[5]), _esc(row[6]))\n        for row in rows\n    )\n    flag = (\'<p class="bad">%s</p>\' % _esc(error)) if error else ""\n    flag += (\'<p class="ok">%s</p>\' % _esc(notice)) if notice else ""\n    return (\n        \'<!doctype html><html><head><meta charset="utf-8"><title>Saini delivery queue</title><style>\'\n        "body{font-family:Arial,sans-serif;max-width:900px;margin:24px auto;padding:16px;background:#f5f7fa;color:#172033}"\n        "main{background:#fff;border:1px solid #d8dee9;border-radius:12px;padding:22px}"\n        "table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:7px}"\n        "button,input{box-sizing:border-box;width:100%;padding:10px;margin-top:6px;font-size:16px}"\n        "button{background:#17365d;color:#fff;border:0;border-radius:8px}"\n        ".ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"\n        "</style></head><body><main><p><a href=\\"/\\">Home</a></p><h1>Saini delivery queue</h1>"\n        "<p>Control stays with Saini. Schools only request. Nothing is activated.</p>"\n        + flag\n        + "<table><tr><th>ID</th><th>School</th><th>Cards</th><th>Marksheets</th><th>Papers</th><th>Status</th><th>Time</th></tr>"\n        + body + "</table>"\n        + \'<form method="post"><input type="hidden" name="csrf_token" value="\' + _esc(token) + \'">\'\n        + \'<label>Order ID</label><input name="order_id" required>\'\n        + \'<button type="submit">Mark dispatched</button></form></main></body></html>\'\n    )\n'
PAIRS = [('import school_registry', 'import school_delivery\nimport school_registry'), ('                    lookup = form.get("student_uid", "").strip().upper()\n                else:\n                    error = "Unknown action"', '                    lookup = form.get("student_uid", "").strip().upper()\n                elif action == "order":\n                    notice = "Request sent to Saini for " + school_delivery.save_order(\n                        conn, school_code, form.get("want_cards"),\n                        form.get("want_marksheets"), form.get("want_papers"),\n                    )\n                else:\n                    error = "Unknown action"'), ('{"paper": "paper", "student": "id", "photo": "id", "marks": "result"}', '{"paper": "paper", "student": "id", "photo": "id", "marks": "result", "order": "output"}'), ('            + "<p>Preview only for " + _esc(school_code) + ". No PDF, no print, and no approval. Status stays DRAFT.</p>"\n            + "<table><tr><th>Item</th><th>Count</th></tr>"\n            + "<tr><td>Paper plans</td><td>" + str(len(papers)) + "</td></tr>"\n            + "<tr><td>ID card students</td><td>" + str(student_count) + "</td></tr>"\n            + "<tr><td>Result marks</td><td>" + str(mark_count) + "</td></tr></table>"\n            + "<h2>Paper plans</h2><table><tr><th>Class</th><th>Subject</th><th>Strength</th><th>Max</th></tr>"\n            + paper_rows + "</table>"', '            + "<p>Saini will prepare and deliver for " + _esc(school_code) + ". The school cannot print. Status stays DRAFT.</p>"\n            + "<table><tr><th>Item</th><th>Count</th></tr>"\n            + "<tr><td>Paper plans</td><td>" + str(len(papers)) + "</td></tr>"\n            + "<tr><td>ID card students</td><td>" + str(student_count) + "</td></tr>"\n            + "<tr><td>Result marks</td><td>" + str(mark_count) + "</td></tr></table>"\n            + "<h2>Paper plans</h2><table><tr><th>Class</th><th>Subject</th><th>Strength</th><th>Max</th></tr>"\n            + paper_rows + "</table>"\n            + "<h2>Send to Saini</h2><form method=\\"post\\">" + hidden\n            + "<input type=\\"hidden\\" name=\\"action\\" value=\\"order\\">"\n            + "<label><input type=\\"checkbox\\" name=\\"want_cards\\" value=\\"1\\"> ID cards</label>"\n            + "<label><input type=\\"checkbox\\" name=\\"want_marksheets\\" value=\\"1\\"> Result marksheets</label>"\n            + "<label><input type=\\"checkbox\\" name=\\"want_papers\\" value=\\"1\\"> Exam paper photostat</label>"\n            + "<button type=\\"submit\\">Send delivery request</button></form>"\n            + school_delivery.orders_table(conn, school_code)'), ('input,select,button{box-sizing:border-box;width:100%;padding:10px;margin-top:4px;font-size:16px}', 'input,select,button{box-sizing:border-box;width:100%;padding:10px;margin-top:4px;font-size:16px}input[type=checkbox]{width:auto;margin-right:8px}')]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL")
    text = DATA.read_text(encoding="utf-8")
    for old, _new in PAIRS:
        if text.count(old) != 1:
            raise SystemExit("ABORT MATCH")
    updated = text
    for old, new in PAIRS:
        updated = updated.replace(old, new, 1)
    app = APP.read_text(encoding="utf-8")
    if "/saini-queue" in app:
        raise SystemExit("ABORT ALREADY")
    if app.count(LINK) != 1:
        raise SystemExit("ABORT LINK " + str(app.count(LINK)))
    marker = 'if __name__ == "__main__":'
    if app.count(marker) != 1:
        raise SystemExit("ABORT MAIN")
    newline = "\r\n" if "\r\n" in app else "\n"
    route = ("\n@app.route(\"/saini-queue\", methods=[\"GET\", \"POST\"])\n"
             "def saini_delivery_queue():\n"
             "    import school_delivery\n"
             "    return school_delivery.saini_queue(get_db, request, session)\n\n")
    app2 = app.replace(LINK, LINK + newline + '<a href="/saini-queue">Saini delivery queue (DEVELOPMENT)</a>', 1)
    app2 = app2.replace(marker, route.replace("\n", newline) + marker, 1)
    if app2.count("/saini-queue") != 2:
        raise SystemExit("ABORT ROUTE")
    tmp = DATA.with_name("school_data.delivery_tmp")
    pyc = DATA.with_name("school_data.delivery_check.pyc")
    atmp = APP.with_name(APP.name + ".delivery_tmp")
    apyc = APP.with_name(APP.name + ".delivery_check.pyc")
    mtmp = MOD.with_name("school_delivery.check.py")
    tmp.write_text(updated, encoding="utf-8", newline="\n")
    atmp.write_text(app2, encoding="utf-8", newline=newline)
    mtmp.write_text(MODULE, encoding="utf-8", newline="\n")
    try:
        py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
        py_compile.compile(str(atmp), cfile=str(apyc), doraise=True)
        py_compile.compile(str(mtmp), doraise=True)
    finally:
        for item in (pyc, apyc):
            if item.exists():
                item.unlink()
    BAK.mkdir(parents=True, exist_ok=True)
    (BAK / "school_data_before_delivery.py").write_bytes(DATA.read_bytes())
    (BAK / "app_before_delivery.py").write_bytes(APP.read_bytes())
    MOD.write_text(MODULE, encoding="utf-8", newline="\n")
    DATA.write_text(updated, encoding="utf-8", newline="\n")
    APP.write_text(app2, encoding="utf-8", newline=newline)
    tmp.unlink(); atmp.unlink(); mtmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("queue=saini")
    print("school_print=no")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()
