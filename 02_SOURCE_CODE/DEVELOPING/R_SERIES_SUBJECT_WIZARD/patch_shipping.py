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
SQL = '    conn.execute(\n        """CREATE TABLE IF NOT EXISTS school_shipping (\n        school_code TEXT PRIMARY KEY, recipient TEXT NOT NULL, mobile TEXT NOT NULL,\n        address TEXT NOT NULL, mode TEXT NOT NULL, confirmed_at TEXT NOT NULL)"""\n    )\n'
FUNCS = 'def save_shipping(conn, school_code, recipient, mobile, address, mode):\n    ensure_orders(conn)\n    _guard_school(conn, school_code)\n    recipient = " ".join(str(recipient or "").split())\n    address = " ".join(str(address or "").split())\n    mode = (mode or "").strip()\n    digits = "".join(ch for ch in str(mobile or "") if ch.isdigit())\n    if len(recipient) < 2 or len(recipient) > 80:\n        raise ValueError("Enter the recipient name")\n    if len(digits) != 10:\n        raise ValueError("Enter a 10 digit mobile number")\n    if len(address) < 10 or len(address) > 200:\n        raise ValueError("Enter the full address")\n    if mode not in ("By hand", "Courier"):\n        raise ValueError("Choose by hand or courier")\n    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    conn.execute(\n        """INSERT INTO school_shipping\n        (school_code, recipient, mobile, address, mode, confirmed_at)\n        VALUES (?,?,?,?,?,?)\n        ON CONFLICT(school_code) DO UPDATE SET\n        recipient=excluded.recipient, mobile=excluded.mobile, address=excluded.address,\n        mode=excluded.mode, confirmed_at=excluded.confirmed_at""",\n        (school_code, recipient, digits, address, mode, _now()),\n    )\n    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]\n    if before != after:\n        conn.rollback()\n        raise ValueError("Refused")\n    conn.commit()\n    return recipient\n\n\ndef shipping_block(conn, school_code, token):\n    ensure_orders(conn)\n    row = conn.execute(\n        "SELECT recipient, mobile, address, mode, confirmed_at FROM school_shipping WHERE school_code=?",\n        (school_code,),\n    ).fetchone()\n    current = (\n        "<p class=\\"bad\\">No shipping address yet. Saini cannot start printing.</p>"\n        if row is None\n        else "<p class=\\"ok\\">Confirmed %s. %s, %s. %s. %s.</p>"\n        % (_esc(row[4]), _esc(row[0]), _esc(row[1]), _esc(row[3]), _esc(row[2]))\n    )\n    return (\n        current\n        + \'<form method="post">\'\n        + \'<input type="hidden" name="csrf_token" value="\' + _esc(token) + \'">\'\n        + \'<input type="hidden" name="action" value="shipping">\'\n        + \'<label>Recipient</label><input name="recipient" required maxlength="80">\'\n        + \'<label>Mobile</label><input name="mobile" required inputmode="numeric" maxlength="10">\'\n        + \'<label>Full address</label><input name="address" required maxlength="200">\'\n        + \'<label>Mode</label><select name="mode"><option>By hand</option><option>Courier</option></select>\'\n        + \'<button type="submit">Confirm address</button></form>\'\n        + "<p>Printing stays closed until this address is confirmed. The school cannot start printing.</p>"\n    )\n\n\n'
CHECK = '        if target == "PRINTING":\n            ready = conn.execute(\n                "SELECT 1 FROM school_shipping WHERE school_code=?",\n                (row[1],),\n            ).fetchone()\n            if ready is None:\n                raise ValueError("School has not confirmed the shipping address")\n'
ACT = '                elif action == "shipping":\n                    notice = "Address confirmed for " + school_delivery.save_shipping(\n                        conn, school_code, form.get("recipient"), form.get("mobile"),\n                        form.get("address"), form.get("mode"),\n                    )\n'
BRANCH = '    elif part == "shipping":\n        body = head + school_delivery.shipping_block(conn, school_code, token)\n'
LINK = '            + \'<a class="go" href="/portal/data?part=shipping">6. Shipping address</a>\'\n'

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
    if "school_shipping" in dtext:
        raise SystemExit("ABORT ALREADY")
    slot = "        mode TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)\"\"\"\n    )\n"
    dtext = once(dtext, slot, slot + SQL, "TABLE")
    dtext = once(dtext, "def advance_order(conn, order_id, action, mode=\"\", note=\"\"):\n", FUNCS + "def advance_order(conn, order_id, action, mode=\"\", note=\"\"):\n", "FUNCS")
    dtext = once(dtext, "        if target == \"DISPATCHED\":\n", CHECK + "        if target == \"DISPATCHED\":\n", "GATE")
    raw = DATA.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    text = once(text, "                elif action == \"payment\":\n", ACT + "                elif action == \"payment\":\n", "ACTION")
    text = once(text, '"payment": "account"}', '"payment": "account", "shipping": "shipping"}', "MAP")
    text = once(text, '("paper", "id", "result", "output", "account")', '("paper", "id", "result", "output", "account", "shipping")', "PART")
    text = once(text, '"output": "Final output"}', '"output": "Final output", "account": "School account", "shipping": "Shipping address"}', "TITLE")
    text = once(text, "    elif part == \"account\":\n        body = head + school_delivery.account_block(conn, school_code, token)\n", "    elif part == \"account\":\n        body = head + school_delivery.account_block(conn, school_code, token)\n" + BRANCH, "PAGE")
    text = once(text, "5. Account</a>'\n", "5. Account</a>'\n" + LINK, "MENU")
    if "save_shipping" not in dtext or "part=shipping" not in text:
        raise SystemExit("ABORT RESULT")
    for path, src_raw, updated, name in (
        (MOD, draw, dtext, "school_delivery.ship_tmp"),
        (DATA, raw, text, "school_data.ship_tmp"),
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
        (BAK / (path.stem + "_before_shipping.py")).write_bytes(src_raw)
        path.write_bytes(tmp.read_bytes())
        tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("print_blocked_until_address=yes")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()

