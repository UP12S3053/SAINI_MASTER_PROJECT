import hashlib, py_compile
from pathlib import Path
DEV = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
MOD = DEV / "school_delivery.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
BAK = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
AH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
BH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
FUNC = 'def _ship_row(conn, school_code):\n    return conn.execute(\n        "SELECT recipient, mobile, address, mode FROM school_shipping WHERE school_code=?",\n        (school_code,),\n    ).fetchone()\n\n\n'
BLOCK = '    ship = _ship_row(conn, row[1])\n    ship_line = (\n        \'<p class="bad">Shipping address is not confirmed. Do not print.</p>\'\n        if ship is None\n        else "<p><b>Ship to:</b> " + _esc(ship[0]) + ", " + _esc(ship[1])\n        + ". " + _esc(ship[3]) + ". " + _esc(ship[2]) + ".</p>"\n    )\n'
CSS_OLD = '"@media print{.noprint{display:none}}img.face{width:78px;height:98px;object-fit:cover;display:block}"\n'
CSS_NEW = '"@media print{.noprint{display:none}}img.face{width:78px;height:98px;object-fit:cover;display:block}"\n        "p.bad{background:#fde8e8;padding:10px}"\n'
LINE_OLD = '        + ". Opened " + _esc(row[6]) + ".</p>"\n        + \'<p class="noprint">'
LINE_NEW = '        + ". Opened " + _esc(row[6]) + ".</p>"\n        + ship_line\n        + \'<p class="noprint">'
HEAD_OLD = '<th>Job</th><th>School</th><th>Cards</th>'
HEAD_NEW = '<th>Job</th><th>School</th><th>Ship to</th><th>Cards</th>'
ROW_OLD = '        body += "<tr><td><a href=\\"\\/saini-queue?job=%s\\">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (\n            row[0], _esc(row[1]), _esc(row[2]), _yes(row[3]), _yes(row[4]), _yes(row[5]),\n            _esc(SCHOOL_LABEL.get(row[6], row[6])), _esc(row[7]), action,\n        )\n'
ROW_NEW = '        ship = _ship_row(conn, row[2])\n        ship_cell = "Not confirmed" if ship is None else "%s, %s, %s" % (ship[0], ship[1], ship[3])\n        body += "<tr><td><a href=\\"/saini-queue?job=%s\\">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (\n            row[0], _esc(row[1]), _esc(row[2]), _esc(ship_cell), _yes(row[3]), _yes(row[4]), _yes(row[5]),\n            _esc(SCHOOL_LABEL.get(row[6], row[6])), _esc(row[7]), action,\n        )\n'

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
    if "_ship_row" in text or "Ship to" in text:
        raise SystemExit("ABORT ALREADY")
    text = once(text, "def _job_card(conn, order_id):\n", FUNC + "def _job_card(conn, order_id):\n", "FUNC")
    text = once(text, "    page = (\n", BLOCK + "    page = (\n", "BLOCK")
    text = once(text, CSS_OLD, CSS_NEW, "CSS")
    text = once(text, LINE_OLD, LINE_NEW, "LINE")
    text = once(text, HEAD_OLD, HEAD_NEW, "HEAD")
    text = once(text, ROW_OLD, ROW_NEW, "ROW")
    if "Not confirmed" not in text or text.count("Ship to") != 2:
        raise SystemExit("ABORT RESULT")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    tmp = MOD.with_name("school_delivery.shipshow_tmp")
    pyc = MOD.with_name("school_delivery.shipshow_tmp.pyc")
    tmp.write_bytes(text.replace("\n", newline).encode("utf-8"))
    try:
        py_compile.compile(str(tmp), cfile=str(pyc), doraise=True)
    finally:
        if pyc.exists():
            pyc.unlink()
    BAK.mkdir(parents=True, exist_ok=True)
    (BAK / "school_delivery_before_ship_show.py").write_bytes(raw)
    MOD.write_bytes(tmp.read_bytes())
    tmp.unlink()
    if sha(ORIG) != AH or sha(DB) != BH:
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("address_on_queue=yes")
    print("address_on_job_card=yes")
    print("original_app=" + sha(ORIG))
    print("original_db=" + sha(DB))
    print("activation_changed=no")

if __name__ == "__main__":
    main()
