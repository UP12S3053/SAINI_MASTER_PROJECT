import hashlib, py_compile
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
MOD = DEV / "school_delivery.py"
DATA = DEV / "school_data.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
AH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
PAIRS = [('import school_registry\n\nNEXT_STATUS', 'import school_registry\n\nCARD_RATE = 20\nSHEET_SIZE = 10\n\nNEXT_STATUS'), ('    blank = conn.execute(\n        "SELECT id, school_code FROM school_delivery_orders WHERE job_code=\'\'"\n    ).fetchall()', '    conn.execute(\n        """CREATE TABLE IF NOT EXISTS school_ledger (\n        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, job_code TEXT NOT NULL,\n        detail TEXT NOT NULL, qty INTEGER NOT NULL, rate INTEGER NOT NULL,\n        amount INTEGER NOT NULL, created_at TEXT NOT NULL)"""\n    )\n    conn.execute(\n        """CREATE TABLE IF NOT EXISTS school_delivery_slots (\n        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, position INTEGER NOT NULL,\n        student_uid TEXT NOT NULL, student_name TEXT NOT NULL, class_name TEXT NOT NULL)"""\n    )\n    blank = conn.execute(\n        "SELECT id, school_code FROM school_delivery_orders WHERE job_code=\'\'"\n    ).fetchall()'), ('def save_order(conn, school_code, cards, sheets, papers):\n', 'def save_card_job(conn, school_code, copies, sheets, papers):\n    ensure_orders(conn)\n    _guard_school(conn, school_code)\n    chosen = []\n    for uid, raw in copies:\n        try:\n            count = int(raw or 0)\n        except ValueError:\n            raise ValueError("Copy count must be 0, 1, 2, or 3")\n        if count < 0 or count > SHEET_SIZE:\n            raise ValueError("Each student can have at most 10 copies on one job")\n        if count:\n            chosen.append((uid, count))\n    total = sum(count for _, count in chosen)\n    if total == 0 and not (sheets or papers):\n        raise ValueError("Choose card copies, marksheets, or exam papers")\n    if total and (total < SHEET_SIZE or total % SHEET_SIZE):\n        raise ValueError(\n            "ID cards print 10 on one A4 sheet. Total is %d. Use double or triple copies until it is 10, 20, or 30."\n            % total\n        )\n    slots = []\n    for uid, count in chosen:\n        student = conn.execute(\n            "SELECT student_name, class_name FROM school_students WHERE school_code=? AND student_uid=?",\n            (school_code, uid),\n        ).fetchone()\n        if student is None:\n            raise ValueError("Student is not in this school")\n        slots.extend((uid, student[0], student[1]) for _ in range(count))\n    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    cursor = conn.execute(\n        """INSERT INTO school_delivery_orders\n        (school_code, want_cards, want_marksheets, want_papers, status, created_at, job_code)\n        VALUES (?,?,?,?,\'REQUESTED\',?,\'\')""",\n        (school_code, 1 if total else 0, 1 if sheets else 0, 1 if papers else 0, _now()),\n    )\n    order_id = cursor.lastrowid\n    job_code = "%s-%04d" % (school_code, order_id)\n    conn.execute("UPDATE school_delivery_orders SET job_code=? WHERE id=?", (job_code, order_id))\n    conn.execute(\n        """INSERT INTO school_delivery_events (order_id, from_status, to_status, created_at)\n        VALUES (?,?,?,?)""",\n        (order_id, "", "REQUESTED", _now()),\n    )\n    for position, slot in enumerate(slots, 1):\n        conn.execute(\n            """INSERT INTO school_delivery_slots\n            (order_id, position, student_uid, student_name, class_name) VALUES (?,?,?,?,?)""",\n            (order_id, position, slot[0], slot[1], slot[2]),\n        )\n    amount = 0\n    if total:\n        amount = total * CARD_RATE\n        names = ", ".join("%s x%d" % pair for pair in chosen)\n        detail = "ID cards, %d A4 sheet, %d cards. %s" % (total // SHEET_SIZE, total, names)\n        conn.execute(\n            """INSERT INTO school_ledger\n            (school_code, job_code, detail, qty, rate, amount, created_at) VALUES (?,?,?,?,?,?,?)""",\n            (school_code, job_code, detail[:500], total, CARD_RATE, amount, _now()),\n        )\n    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    if before != after:\n        conn.rollback()\n        raise ValueError("Refused")\n    conn.commit()\n    return job_code, amount\n\n\ndef card_job_form(conn, school_code, token):\n    rows = conn.execute(\n        """SELECT student_uid, class_name, student_name FROM school_students\n        WHERE school_code=? ORDER BY class_name, student_name""",\n        (school_code,),\n    ).fetchall()\n    lines = ""\n    for uid, class_name, student_name in rows:\n        lines += (\n            "<tr><td>%s</td><td>%s</td><td>%s</td><td><select style=\\"width:90px\\" name=\\"copy_%s\\" onchange=\\"tally()\\">"\n            "<option>0</option><option>1</option><option>2</option><option>3</option>"\n            "<option>4</option><option>5</option><option>6</option><option>7</option>"\n            "<option>8</option><option>9</option><option>10</option></select></td></tr>"\n            % (_esc(uid), _esc(class_name), _esc(student_name), _esc(uid))\n        )\n    return (\n        "<h2>ID card A4 job</h2><p>Production prints 10 cards on one A4 sheet, 2 by 5. "\n        "A job needs 10, 20, or 30 cards. Copy one student 2 or 3 times to fill the sheet. "\n        "Rate is Rs %d per card. The school account updates when the job is created.</p>"\n        % CARD_RATE\n        + \'<form method="post">\'\n        + \'<input type="hidden" name="csrf_token" value="\' + _esc(token) + \'">\'\n        + \'<input type="hidden" name="action" value="cardsheet">\'\n        + "<table><tr><th>UID</th><th>Class</th><th>Student</th><th>Copies</th></tr>"\n        + lines + "</table><p id=\\"tally\\">0 cards</p>"\n        + \'<label><input type="checkbox" name="want_marksheets" value="1"> Result marksheets</label>\'\n        + \'<label><input type="checkbox" name="want_papers" value="1"> Exam paper photostat</label>\'\n        + \'<button type="submit">Create A4 job</button></form>\'\n        + "<script>function tally(){var n=0,nodes=document.querySelectorAll(\'select[name^=copy_]\');"\n        + "for(var i=0;i<nodes.length;i++)n+=+nodes[i].value;var ok=n>=10&&n%10==0;"\n        + "document.getElementById(\'tally\').textContent=n+\' cards\'"\n        + "+(ok?\', \'+n/10+\' A4 sheet, Rs \'+(n*" + str(CARD_RATE) + "):\'. Need 10, 20, or 30.\');}</script>"\n    )\n\n\ndef account_block(conn, school_code):\n    ensure_orders(conn)\n    rows = conn.execute(\n        """SELECT created_at, job_code, detail, qty, rate, amount\n        FROM school_ledger WHERE school_code=? ORDER BY id""",\n        (school_code,),\n    ).fetchall()\n    body = "".join(\n        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"\n        % (_esc(row[0]), _esc(row[1]), _esc(row[2]), row[3], row[4], row[5])\n        for row in rows\n    )\n    total = sum(row[5] for row in rows)\n    return (\n        "<h1>School account</h1><p>Showing only " + _esc(school_code)\n        + ". This khata updates by itself when an ID card job is created. Rate Rs %d per card.</p>"\n        % CARD_RATE\n        + "<table><tr><th>Date</th><th>Job</th><th>Detail</th><th>Cards</th><th>Rate</th><th>Amount</th></tr>"\n        + body + "</table><h2>Balance due</h2><p>Rs %d</p>" % total\n        + \'<p><a href="/portal/data">School data</a></p>\'\n    )\n\n\ndef _slot_sheet(conn, order_id, school_code):\n    rows = conn.execute(\n        """SELECT position, student_uid, class_name, student_name\n        FROM school_delivery_slots WHERE order_id=? ORDER BY position""",\n        (order_id,),\n    ).fetchall()\n    if not rows:\n        return ""\n    body = ""\n    sheet = 0\n    for position, uid, class_name, student_name in rows:\n        if (position - 1) % SHEET_SIZE == 0:\n            sheet += 1\n            body += \'<tr><td colspan="5"><strong>A4 sheet %d, 2 x 5</strong></td></tr>\' % sheet\n        body += "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (\n            ((position - 1) % SHEET_SIZE) + 1, _esc(uid), _esc(class_name), _esc(student_name),\n            _face(conn, school_code, uid, uid),\n        )\n    return (\n        "<h2>ID cards</h2><table><tr><th>Place</th><th>UID</th><th>Class</th><th>Student</th><th>Photo</th></tr>"\n        + body + "</table>"\n    )\n\n\ndef save_order(conn, school_code, cards, sheets, papers):\n'), ('    flags = (1 if cards else 0, 1 if sheets else 0, 1 if papers else 0)\n', '    if cards:\n        raise ValueError("ID cards print 10 on one A4 sheet. Use the card job form, not this tick box.")\n    flags = (0, 1 if sheets else 0, 1 if papers else 0)\n'), ('        sections += _card_sheet(conn, row[1])\n', '        order_pk = conn.execute(\n            "SELECT id FROM school_delivery_orders WHERE job_code=?", (row[0],)\n        ).fetchone()[0]\n        sections += _slot_sheet(conn, order_pk, row[1]) or _card_sheet(conn, row[1])\n')]
FORM_OLD = '            + "<h2>Send to Saini</h2><form method=\\"post\\">" + hidden\n            + "<input type=\\"hidden\\" name=\\"action\\" value=\\"order\\">"\n            + "<label><input type=\\"checkbox\\" name=\\"want_cards\\" value=\\"1\\"> ID cards</label>"\n            + "<label><input type=\\"checkbox\\" name=\\"want_marksheets\\" value=\\"1\\"> Result marksheets</label>"\n            + "<label><input type=\\"checkbox\\" name=\\"want_papers\\" value=\\"1\\"> Exam paper photostat</label>"\n            + "<button type=\\"submit\\">Send delivery request</button></form>"\n'
FORM_NEW = '            + school_delivery.card_job_form(conn, school_code, token)\n'
CARDS = '                elif action == "cardsheet":\n                    copies = [(key[5:], form.get(key)) for key in form if key.startswith("copy_")]\n                    job_code, amount = school_delivery.save_card_job(\n                        conn, school_code, copies, form.get("want_marksheets"), form.get("want_papers"),\n                    )\n                    notice = "A4 job " + job_code + " created. Account increased by Rs " + str(amount) + "."\n'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def once(text, old, new, name):
    if text.count(old) != 1:
        raise SystemExit("ABORT " + name)
    return text.replace(old, new, 1)

def main():
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL")
    draw = MOD.read_bytes()
    dtext = draw.decode("utf-8").replace("\r\n", "\n")
    if "CARD_RATE" in dtext:
        raise SystemExit("ABORT ALREADY")
    for old, new in PAIRS:
        dtext = once(dtext, old, new, "DELIVERY")
    data_raw = DATA.read_bytes()
    text = data_raw.decode("utf-8").replace("\r\n", "\n")
    if "import school_delivery" not in text:
        text = once(text, "import school_registry\n", "import school_registry\nimport school_delivery\n", "IMPORT")
    text = once(text, "                elif action == \"order\":\n", CARDS + "                elif action == \"order\":\n", "ACTION")
    text = once(text, '"order": "output"}', '"order": "output", "cardsheet": "output"}', "MAP")
    text = once(text, '("paper", "id", "result", "output")', '("paper", "id", "result", "output", "account")', "PART")
    text = once(text, FORM_OLD, FORM_NEW, "FORM")
    account_old_a = "            + orders_table(conn, school_code)\n        )\n    else:\n"
    account_old_b = "            + school_delivery.orders_table(conn, school_code)\n        )\n    else:\n"
    account_new = "            + school_delivery.orders_table(conn, school_code)\n        )\n    elif part == \"account\":\n        body = head + school_delivery.account_block(conn, school_code)\n    else:\n"
    if text.count(account_old_a) == 1:
        text = text.replace(account_old_a, account_new, 1)
    elif text.count(account_old_b) == 1:
        text = text.replace(account_old_b, account_new, 1)
    else:
        raise SystemExit("ABORT ACCOUNT")
    text = once(text, '">4. Final output</a>\'\n', '">4. Final output</a>\'\n            + \'<a class="go" href="/portal/data?part=account">5. Account</a>\'\n', "MENU")
    if "def save_card_job" not in dtext or "card_job_form" not in text or "part == \"account\"" not in text:
        raise SystemExit("ABORT RESULT")
    for path, raw, updated, name in (
        (MOD, draw, dtext, "school_delivery.a4_tmp"),
        (DATA, data_raw, text, "school_data.a4_tmp"),
    ):
        newline = "\r\n" if b"\r\n" in raw else "\n"
        tmp = path.with_name(name)
        pyc = path.with_name(name + ".pyc")
        tmp.write_bytes(updated.replace("\n", newline).encode("utf-8"))
        try:
            py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
        finally:
            if pyc.exists():
                pyc.unlink()
        BAK.mkdir(parents=True, exist_ok=True)
        (BAK / (path.name.replace(".py", "_before_a4.py"))).write_bytes(raw)
        path.write_bytes(tmp.read_bytes())
        tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("a4=10")
    print("rate=20")
    print("account=auto")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()
