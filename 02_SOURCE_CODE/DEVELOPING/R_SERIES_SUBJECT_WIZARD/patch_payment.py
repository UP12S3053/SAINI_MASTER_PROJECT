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
PAYSQL = '    conn.execute(\n        """CREATE TABLE IF NOT EXISTS school_payments (\n        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, amount INTEGER NOT NULL,\n        status TEXT NOT NULL, image_path TEXT NOT NULL, created_at TEXT NOT NULL,\n        approved_at TEXT NOT NULL DEFAULT \'\')"""\n    )\n'
FUNCS = 'def _money(conn, school_code):\n    ensure_orders(conn)\n    charges = conn.execute(\n        "SELECT COALESCE(SUM(amount),0) FROM school_ledger WHERE school_code=?",\n        (school_code,),\n    ).fetchone()[0]\n    approved = conn.execute(\n        "SELECT COALESCE(SUM(amount),0) FROM school_payments WHERE school_code=? AND status=\'APPROVED\'",\n        (school_code,),\n    ).fetchone()[0]\n    pending = conn.execute(\n        "SELECT COALESCE(SUM(amount),0) FROM school_payments WHERE school_code=? AND status=\'PENDING\'",\n        (school_code,),\n    ).fetchone()[0]\n    return charges, approved, pending, charges - approved\n\n\ndef _proof_img(conn, stored):\n    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent\n    path = (root / stored).resolve()\n    if root not in path.parents or not path.is_file():\n        return ""\n    raw = path.read_bytes()\n    if len(raw) > 1500000:\n        return "Too large to preview"\n    kind = "png" if raw.startswith(b"\\x89PNG") else "jpeg"\n    return \'<img style="width:140px;height:auto" alt="" src="data:image/\' + kind + \';base64,\' + base64.b64encode(raw).decode("ascii") + \'">\'\n\n\ndef save_payment(conn, school_code, amount, proof):\n    ensure_orders(conn)\n    _guard_school(conn, school_code)\n    try:\n        rupees = int(str(amount).strip())\n    except (TypeError, ValueError):\n        raise ValueError("Enter the amount in rupees")\n    if rupees < 1:\n        raise ValueError("Enter the amount in rupees")\n    charges, approved, pending, due = _money(conn, school_code)\n    if rupees > due - pending:\n        raise ValueError("Amount is more than the balance still open")\n    if proof is None or not getattr(proof, "filename", ""):\n        raise ValueError("Upload the PhonePe screenshot")\n    raw = proof.read()\n    if not raw or len(raw) > 1500000:\n        raise ValueError("Screenshot must be a JPG or PNG under 1.5 MB")\n    if raw.startswith(b"\\xff\\xd8\\xff"):\n        suffix = ".jpg"\n    elif raw.startswith(b"\\x89PNG"):\n        suffix = ".png"\n    else:\n        raise ValueError("Screenshot must be a JPG or PNG")\n    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    cursor = conn.execute(\n        """INSERT INTO school_payments\n        (school_code, amount, status, image_path, created_at, approved_at)\n        VALUES (?,?,\'PENDING\',\'\',?,\'\')""",\n        (school_code, rupees, _now()),\n    )\n    payment_id = cursor.lastrowid\n    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent\n    folder = (root / "school_payments" / school_code).resolve()\n    folder.mkdir(parents=True, exist_ok=True)\n    target = (folder / ("%d%s" % (payment_id, suffix))).resolve()\n    if folder not in target.parents:\n        conn.rollback()\n        raise ValueError("Unsafe payment path")\n    target.write_bytes(raw)\n    relative = target.relative_to(root).as_posix()\n    conn.execute("UPDATE school_payments SET image_path=? WHERE id=?", (relative, payment_id))\n    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    if before != after:\n        conn.rollback()\n        raise ValueError("Refused")\n    conn.commit()\n    return "Rs %d pending for approval" % rupees\n\n\ndef approve_payment(conn, payment_id):\n    ensure_orders(conn)\n    row = conn.execute(\n        "SELECT amount, status FROM school_payments WHERE id=?",\n        (payment_id,),\n    ).fetchone()\n    if row is None or row[1] != "PENDING":\n        raise ValueError("Payment is not waiting")\n    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    changed = conn.execute(\n        "UPDATE school_payments SET status=\'APPROVED\', approved_at=? WHERE id=? AND status=\'PENDING\'",\n        (_now(), payment_id),\n    ).rowcount\n    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    if changed != 1 or before != after:\n        conn.rollback()\n        raise ValueError("Refused")\n    conn.commit()\n    return row[0]\n\n\n'
OLDBODY = '    total = sum(row[5] for row in rows)\n    return (\n        "<h1>School account</h1><p>Showing only " + _esc(school_code)\n        + ". This khata updates by itself when an ID card job is created. Rate Rs %d per card.</p>"\n        % CARD_RATE\n        + "<table><tr><th>Date</th><th>Job</th><th>Detail</th><th>Cards</th><th>Rate</th><th>Amount</th></tr>"\n        + body + "</table><h2>Balance due</h2><p>Rs %d</p>" % total\n        + \'<p><a href="/portal/data">School data</a></p>\'\n    )\n'
NEWBODY = '    total = sum(row[5] for row in rows)\n    charges, approved, pending, due = _money(conn, school_code)\n    proofs = conn.execute(\n        """SELECT created_at, amount, status, image_path FROM school_payments\n        WHERE school_code=? ORDER BY id DESC""",\n        (school_code,),\n    ).fetchall()\n    proof_rows = "".join(\n        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"\n        % (\n            _esc(item[0]), item[1],\n            "Rs %d pending for approval" % item[1] if item[2] == "PENDING" else "Approved",\n            _proof_img(conn, item[3]),\n        )\n        for item in proofs\n    )\n    return (\n        "<h1>School account</h1><p>Showing only " + _esc(school_code)\n        + ". This khata updates by itself when an ID card job is created. Rate Rs %d per card.</p>"\n        % CARD_RATE\n        + "<table><tr><th>Date</th><th>Job</th><th>Detail</th><th>Cards</th><th>Rate</th><th>Amount</th></tr>"\n        + body + "</table>"\n        + "<h2>Payments</h2><table><tr><th>Date</th><th>Amount</th><th>Status</th><th>Screenshot</th></tr>"\n        + proof_rows + "</table>"\n        + \'<h2>Send PhonePe proof</h2><form method="post" enctype="multipart/form-data">\'\n        + \'<input type="hidden" name="csrf_token" value="\' + _esc(token) + \'">\'\n        + \'<input type="hidden" name="action" value="payment">\'\n        + \'<label>Amount paid, Rs</label><input name="amount" inputmode="numeric" required>\'\n        + \'<label>Payment screenshot</label><input name="proof" type="file" accept="image/jpeg,image/png" required>\'\n        + \'<button type="submit">Upload screenshot</button></form>\'\n        + "<h2>Balance due</h2><p>Rs %d</p>" % due\n        + "<p>Pending Rs %d is not deducted until Saini approves it. Charges Rs %d. Approved Rs %d.</p>"\n        % (pending, charges, approved)\n        + \'<p><a href="/portal/data">School data</a></p>\'\n    )\n\n'
OLDTRY = '            try:\n                target = advance_order(\n                    conn, int(request.form.get("order_id", "0")), request.form.get("action", "")\n                )\n                notice = "Job moved to " + SCHOOL_LABEL.get(target, target)\n'
NEWTRY = '            try:\n                action = request.form.get("action", "")\n                if action == "approve_payment":\n                    paid = approve_payment(conn, int(request.form.get("payment_id", "0")))\n                    notice = "Payment approved. Rs %d deducted from the school balance." % paid\n                else:\n                    target = advance_order(\n                        conn, int(request.form.get("order_id", "0")), action\n                    )\n                    notice = "Job moved to " + SCHOOL_LABEL.get(target, target)\n'
PAYBLOCK = '    waiting = conn.execute(\n        """SELECT id, school_code, amount, created_at, image_path\n        FROM school_payments WHERE status=\'PENDING\' ORDER BY id"""\n    ).fetchall()\n    pay_rows = "".join(\n        "<tr><td>%s</td><td>%s</td><td>Rs %d pending for approval</td><td>%s</td><td>"\n        % (_esc(item[1]), _esc(item[3]), item[2], _proof_img(conn, item[4]))\n        + \'<form method="post"><input type="hidden" name="csrf_token" value="%s">\'\n        % _esc(token)\n        + \'<input type="hidden" name="action" value="approve_payment">\'\n        + \'<input type="hidden" name="payment_id" value="%d">\' % item[0]\n        + \'<button type="submit">Approve</button></form></td></tr>\'\n        for item in waiting\n    )\n    pay_table = (\n        "<h2>Payments waiting</h2><table><tr><th>School</th><th>Time</th><th>Status</th><th>Screenshot</th><th></th></tr>"\n        + pay_rows + "</table>"\n    )\n'
PAYACT = """                elif action == \"payment\":
                    notice = school_delivery.save_payment(
                        conn, school_code, form.get(\"amount\"), request.files.get(\"proof\"),
                    )
"""

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
    if "save_payment" in dtext:
        raise SystemExit("ABORT ALREADY")
    slot = "        student_uid TEXT NOT NULL, student_name TEXT NOT NULL, class_name TEXT NOT NULL)\"\"\"\n    )\n"
    dtext = once(dtext, slot, slot + PAYSQL, "TABLE")
    dtext = once(dtext, "def account_block(conn, school_code):\n", FUNCS + "def account_block(conn, school_code, token):\n", "FUNCS")
    dtext = once(dtext, OLDBODY, NEWBODY, "ACCOUNT")
    dtext = once(dtext, OLDTRY, NEWTRY, "QUEUE")
    dtext = once(dtext, "    filters += \"</p>\"\n    flag = ", "    filters += \"</p>\"\n" + PAYBLOCK + "    flag = ", "WAITING")
    dtext = once(dtext, "        + filters + flag\n", "        + filters + flag + pay_table\n", "SHOW")
    raw = DATA.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    text = once(text, "                elif action == \"cardsheet\":\n", PAYACT + "                elif action == \"cardsheet\":\n", "ACTION")
    text = once(text, '"cardsheet": "output"}', '"cardsheet": "output", "payment": "account"}', "MAP")
    text = once(text, "school_delivery.account_block(conn, school_code)", "school_delivery.account_block(conn, school_code, token)", "CALL")
    if "save_payment" not in dtext or "approve_payment" not in text and "action == \"payment\"" not in text:
        raise SystemExit("ABORT RESULT")
    for path, src_raw, updated, name in (
        (MOD, draw, dtext, "school_delivery.pay_tmp"),
        (DATA, raw, text, "school_data.pay_tmp"),
    ):
        newline = "\r\n" if b"\r\n" in src_raw else "\n"
        tmp = path.with_name(name)
        pyc = path.with_name(name + ".pyc")
        tmp.write_bytes(updated.replace("\n", newline).encode("utf-8"))
        try:
            py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
        finally:
            if pyc.exists():
                pyc.unlink()
        BAK.mkdir(parents=True, exist_ok=True)
        (BAK / (path.stem + "_before_payment.py")).write_bytes(src_raw)
        path.write_bytes(tmp.read_bytes())
        tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("payment=pending")
    print("approve=saini")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()
