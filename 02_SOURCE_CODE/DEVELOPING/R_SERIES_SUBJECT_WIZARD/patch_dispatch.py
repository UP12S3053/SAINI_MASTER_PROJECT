import hashlib, py_compile
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
MOD = DEV / "school_delivery.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
AH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
SQL = '    conn.execute(\n        """CREATE TABLE IF NOT EXISTS school_dispatch (\n        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL UNIQUE,\n        mode TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)"""\n    )\n'
CHECK = '        if target == "DISPATCHED":\n            mode = (mode or "").strip()\n            note = " ".join(str(note or "").split())\n            if mode not in ("By hand", "Courier"):\n                raise ValueError("Choose by hand or courier")\n            if len(note) < 2 or len(note) > 80:\n                raise ValueError("Enter the person name or tracking number")\n'
INSERT = '    if target == "DISPATCHED":\n        conn.execute(\n            "INSERT INTO school_dispatch (order_id, mode, note, created_at) VALUES (?,?,?,?)",\n            (order_id, mode, note, _now()),\n        )\n'
OLDORD = '    rows = conn.execute(\n        """SELECT job_code, want_cards, want_marksheets, want_papers, status, created_at\n        FROM school_delivery_orders WHERE school_code=? ORDER BY id DESC""",\n        (school_code,),\n    ).fetchall()\n    body = "".join(\n        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"\n        % (_esc(row[0]), _yes(row[1]), _yes(row[2]), _yes(row[3]), _esc(SCHOOL_LABEL.get(row[4], row[4])), _esc(row[5]))\n        for row in rows\n    )\n    return (\n        "<h2>Delivery jobs</h2><table><tr><th>Job</th><th>ID cards</th><th>Marksheets</th>"\n        "<th>Papers</th><th>Stage</th><th>Time</th></tr>" + body + "</table>"\n        + "<p>Saini prints, checks, packs, and dispatches. The school cannot print.</p>"\n    )\n'
NEWORD = '    rows = conn.execute(\n        """SELECT o.job_code, o.want_cards, o.want_marksheets, o.want_papers, o.status, o.created_at,\n        IFNULL(d.mode, \'\'), IFNULL(d.note, \'\')\n        FROM school_delivery_orders o\n        LEFT JOIN school_dispatch d ON d.order_id=o.id\n        WHERE o.school_code=? ORDER BY o.id DESC""",\n        (school_code,),\n    ).fetchall()\n    body = "".join(\n        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"\n        % (\n            _esc(row[0]), _yes(row[1]), _yes(row[2]), _yes(row[3]),\n            _esc(SCHOOL_LABEL.get(row[4], row[4])), _esc(row[5]),\n            _esc((row[6] + " " + row[7]).strip()),\n        )\n        for row in rows\n    )\n    return (\n        "<h2>Delivery jobs</h2><table><tr><th>Job</th><th>ID cards</th><th>Marksheets</th>"\n        "<th>Papers</th><th>Stage</th><th>Time</th><th>Dispatch</th></tr>" + body + "</table>"\n        + "<p>Saini prints, checks, packs, and dispatches. The school can see the stage but cannot change it.</p>"\n    )\n\n\n'
FORM = 'def _dispatch_form(token, order_id):\n    return (\n        \'<form method="post">\'\n        + \'<input type="hidden" name="csrf_token" value="\' + _esc(token) + \'">\'\n        + \'<input type="hidden" name="order_id" value="\' + str(order_id) + \'">\'\n        + \'<input type="hidden" name="action" value="next">\'\n        + \'<select name="dispatch_mode"><option>By hand</option><option>Courier</option></select>\'\n        + \'<input name="dispatch_note" maxlength="80" required placeholder="Person or tracking">\'\n        + \'<button type="submit">Dispatch</button></form>\'\n    )\n\n\n'
OLDCALL = '                    target = advance_order(\n                        conn, int(request.form.get("order_id", "0")), action\n                    )\n'
NEWCALL = '                    target = advance_order(\n                        conn, int(request.form.get("order_id", "0")), action,\n                        request.form.get("dispatch_mode", ""),\n                        request.form.get("dispatch_note", ""),\n                    )\n'
OLDBR = '        if row[6] in NEXT_LABEL:\n            action = _button(token, row[0], "next", NEXT_LABEL[row[6]])\n'
NEWBR = '        if row[6] == "PACKED":\n            action = _dispatch_form(token, row[0])\n        elif row[6] in NEXT_LABEL:\n            action = _button(token, row[0], "next", NEXT_LABEL[row[6]])\n'
OLDPAY = '        + \'<button type="submit">Approve</button></form></td></tr>\'\n        for item in waiting\n    )\n'
NEWPAY = '        + \'<button type="submit">Approve</button></form></td></tr>\'\n        for item in waiting\n    ) or \'<tr><td colspan="5">No payment is waiting.</td></tr>\'\n'
OLDCSS = '"button{background:#17365d;color:#fff;border:0;border-radius:8px;padding:8px 12px;width:auto}"'
NEWCSS = '"button,select,input{background:#17365d;color:#fff;border:0;border-radius:8px;padding:8px 12px;width:auto}"\n        "select,input{background:#fff;color:#172033;border:1px solid #d8dee9;margin:0 6px 6px 0}"\n        '

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
    if "school_dispatch" in text or "_dispatch_form" in text:
        raise SystemExit("ABORT ALREADY")
    slot = "        approved_at TEXT NOT NULL DEFAULT '')\"\"\"\n    )\n"
    text = once(text, slot, slot + SQL, "TABLE")
    text = once(text, "def advance_order(conn, order_id, action):", 'def advance_order(conn, order_id, action, mode="", note=""):', "SIGN")
    anchor = '        if not target:\n            raise ValueError("This job is already dispatched")\n'
    text = once(text, anchor, anchor + CHECK, "CHECK")
    mid = "        (order_id, current, target, _now()),\n    )\n    after = conn.execute(\"SELECT COUNT(*) FROM school_accounts WHERE activated!=0\").fetchone()[0]\n"
    text = once(text, mid, "        (order_id, current, target, _now()),\n    )\n" + INSERT + "    after = conn.execute(\"SELECT COUNT(*) FROM school_accounts WHERE activated!=0\").fetchone()[0]\n", "SAVE")
    text = once(text, OLDORD, NEWORD, "SCHOOL")
    text = once(text, "def saini_queue(get_db, request, session):\n", FORM + "def saini_queue(get_db, request, session):\n", "FORM")
    text = once(text, OLDCALL, NEWCALL, "CALL")
    text = once(text, OLDBR, NEWBR, "BUTTON")
    text = once(text, OLDPAY, NEWPAY, "EMPTY")
    text = once(text, OLDCSS + "\n        ", NEWCSS, "CSS")
    if "school_dispatch" not in text or "_dispatch_form" not in text:
        raise SystemExit("ABORT RESULT")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    tmp = MOD.with_name("school_delivery.dispatch_tmp")
    pyc = MOD.with_name("school_delivery.dispatch_tmp.pyc")
    tmp.write_bytes(text.replace("\n", newline).encode("utf-8"))
    try:
        py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
    finally:
        if pyc.exists():
            pyc.unlink()
    BAK.mkdir(parents=True, exist_ok=True)
    (BAK / "school_delivery_before_dispatch.py").write_bytes(raw)
    MOD.write_bytes(tmp.read_bytes())
    tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("dispatch=by-hand-or-courier")
    print("school_stage=read_only")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()

