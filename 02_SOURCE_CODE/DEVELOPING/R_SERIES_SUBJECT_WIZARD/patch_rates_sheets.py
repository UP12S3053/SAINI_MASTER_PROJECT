# -*- coding: utf-8 -*-
"""Per-school paper rates, sheet multiplier, and removal of the duplicate Rs 400 line."""
import hashlib
import py_compile
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
DEV = APP.parent
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
DEV_DB = DEV / "paper_bank.db"
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
PAPER_CODE = "BSM-UKG-MAT-20261030-AGMO"
RATES = r'''# -*- coding: utf-8 -*-
"""Paper prices belong to Saini. A school cannot change its own rate."""
import struct
import zipfile
from pathlib import Path


def ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_paper_rates (
            school_code TEXT PRIMARY KEY,
            master_rate INTEGER NOT NULL,
            copy_rate INTEGER NOT NULL
        )"""
    )
    conn.commit()


def rates_for(conn, school_code):
    ensure(conn)
    code = (school_code or "").strip().upper()
    row = conn.execute(
        "SELECT master_rate, copy_rate FROM school_paper_rates WHERE school_code=?",
        (code,),
    ).fetchone()
    if row is None:
        return 10, 1
    return int(row[0]), int(row[1])


def set_rates(conn, school_code, master_rate, copy_rate):
    ensure(conn)
    code = (school_code or "").strip().upper()
    if not code or len(code) > 20:
        raise ValueError("School code is required")
    master = int(master_rate)
    copy = int(copy_rate)
    if master < 0 or master > 500 or copy < 0 or copy > 500:
        raise ValueError("Rate must be from 0 to 500")
    conn.execute(
        """INSERT INTO school_paper_rates (school_code, master_rate, copy_rate)
        VALUES (?,?,?)
        ON CONFLICT(school_code) DO UPDATE SET
        master_rate=excluded.master_rate, copy_rate=excluded.copy_rate""",
        (code, master, copy),
    )
    conn.commit()
    return code, master, copy


def sheets_in_docx(path):
    path = Path(path)
    if not path.is_file():
        return 1
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        return 1
    full = 0
    strips = 0
    for name in archive.namelist():
        if not name.startswith("word/media/"):
            continue
        data = archive.read(name)
        height = 0
        if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
            height = struct.unpack(">I", data[20:24])[0]
        if height >= 1200:
            full += 1
        else:
            strips += 1
    sheets = full + ((strips + 4) // 5 if strips else 0)
    if sheets < 1:
        sheets = 1
    if sheets > 12:
        sheets = 12
    return sheets
'''

ROUTE = r'''
@app.route("/saini/paper-rates", methods=["GET", "POST"])
def saini_paper_rates():
    import paper_rates
    if not session.get("saini_teacher_authenticated"):
        return redirect(url_for("trial_login", next="/saini/paper-rates"))
    conn = get_db()
    paper_rates.ensure(conn)
    message = ""
    error = ""
    if request.method == "POST":
        try:
            saved = paper_rates.set_rates(
                conn,
                request.form.get("school_code", ""),
                request.form.get("master_rate", ""),
                request.form.get("copy_rate", ""),
            )
            message = "Saved %s. Master Rs %s, copy Rs %s. The next paper uses this rate." % saved
        except (TypeError, ValueError) as exc:
            error = str(exc)
    rows = conn.execute(
        "SELECT school_code, master_rate, copy_rate FROM school_paper_rates ORDER BY school_code"
    ).fetchall()
    body = "".join("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % row for row in rows)
    flag = ""
    if error:
        flag += '<p class="bad">%s</p>' % error
    if message:
        flag += '<p class="ok">%s</p>' % message
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><title>Paper rates</title>'
        '<style>body{font-family:Arial;max-width:760px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}'
        'main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}'
        'input,button{box-sizing:border-box;padding:11px;margin:6px 6px 0 0;font-size:16px}'
        'button{background:#17365d;color:white;border:0;border-radius:8px}'
        'table{width:100%;border-collapse:collapse;margin-top:12px}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px}'
        '.ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}</style></head><body><main>'
        '<p><a href="/">Home</a></p><h1>Paper rates</h1>'
        '<p>Only Saini can change a rate. A school cannot. No saved row means master Rs 10 and copy Rs 1. Copies = students x sheets.</p>'
        + flag
        + '<form method="post"><label>School code</label><br><input name="school_code" required maxlength="20">'
        '<br><label>Master rate</label><br><input name="master_rate" value="10" inputmode="numeric" required>'
        '<br><label>Copy rate</label><br><input name="copy_rate" value="1" inputmode="numeric" required>'
        '<br><button type="submit">Save rate</button></form>'
        '<table><tr><th>School</th><th>Master</th><th>Copy</th></tr>' + body + '</table></main></body></html>'
    )
    return page

'''


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_bill(text):
    if text.count("_billed_copies") != 0:
        raise SystemExit("ABORT ALREADY")
    key = '_master = "Paper master %s %s" % (_class_name, _subject_name)'
    if text.count(key) != 1:
        raise SystemExit("ABORT MASTER_COUNT %s" % text.count(key))
    master_tuple = "(_school_name, _paper_code, _master, 1, 10, 10, _stamp),"
    copy_tuple = "(_school_name, _paper_code, _copy_line, _copies, 1, _copies, _stamp),"
    copy_line = '_copy_line = "Paper copies %s %s %s" % (_class_name, _subject_name, _paper_code)'
    copy_if = 'if _copies > 0 and _bill.execute("SELECT 1 FROM school_ledger WHERE school_code=? AND detail=? LIMIT 1", (_school_name, _copy_line)).fetchone() is None:'
    note = '"School %s\\nClass %s\\nSubject %s\\nPaper %s\\nMaster Rs 10 once for this subject\\nCopies %s x Rs 1\\nNot an ID card job\\n" % (_school_name, _class_name, _subject_name, _paper_code, _copies),'
    for name, item in (("TUPLE_M", master_tuple), ("TUPLE_C", copy_tuple), ("LINE", copy_line), ("IF", copy_if), ("NOTE", note)):
        if text.count(item) != 1:
            raise SystemExit("ABORT %s %s" % (name, text.count(item)))
    start = text.find(key)
    line_start = text.rfind("\n", 0, start) + 1
    indent = text[line_start:start]
    calc = (
        indent + "import paper_rates as _paper_rates\n"
        + indent + "_master_rate, _copy_rate = _paper_rates.rates_for(_bill, _school_name)\n"
        + indent + "_sheets = _paper_rates.sheets_in_docx(fpath)\n"
        + indent + "_students = _copies\n"
        + indent + "_billed_copies = _students * _sheets\n"
    )
    text = text[:line_start] + calc + text[line_start:]
    text = text.replace(master_tuple, "(_school_name, _paper_code, _master, 1, _master_rate, _master_rate, _stamp),", 1)
    text = text.replace(
        copy_line,
        '_copy_line = "Paper copies %s %s %s %s students x %s sheets" % (_class_name, _subject_name, _paper_code, _students, _sheets)',
        1,
    )
    text = text.replace(
        copy_if,
        'if _billed_copies > 0 and _bill.execute("SELECT 1 FROM school_ledger WHERE school_code=? AND detail=? LIMIT 1", (_school_name, _copy_line)).fetchone() is None:',
        1,
    )
    text = text.replace(copy_tuple, "(_school_name, _paper_code, _copy_line, _billed_copies, _copy_rate, _billed_copies * _copy_rate, _stamp),", 1)
    text = text.replace(
        note,
        '"School %s\\nClass %s\\nSubject %s\\nPaper %s\\nMaster Rs %s once for this subject\\n%s students x %s sheets x Rs %s\\nNot an ID card job\\n" % (_school_name, _class_name, _subject_name, _paper_code, _master_rate, _students, _sheets, _copy_rate),',
        1,
    )
    if text.count("_billed_copies") != 4:
        raise SystemExit("ABORT BILLED %s" % text.count("_billed_copies"))
    return text


def add_route(text):
    if "/saini/paper-rates" in text:
        raise SystemExit("ABORT ROUTE_EXISTS")
    marker = 'if __name__ == "__main__":'
    if text.count(marker) != 1:
        raise SystemExit("ABORT MAIN %s" % text.count(marker))
    text = text.replace(marker, ROUTE + "\n" + marker, 1)
    heading = "<h1>Central production queue</h1>"
    portal = '<a href="/school-login">School Portal (DEVELOPMENT)</a>'
    link = '<p><a href="/saini/paper-rates">Paper rates (SAINI)</a></p>'
    if text.count(heading) == 1:
        text = text.replace(heading, heading + link, 1)
    elif text.count(portal) == 1:
        text = text.replace(portal, portal + "\n" + link, 1)
    else:
        raise SystemExit("ABORT LINK")
    card = "Rate Rs 20 per card."
    if text.count(card) == 1:
        text = text.replace(
            card,
            "Rate Rs 20 per card. Paper rates are set by Saini for each school. If one paper needs 2, 3 or 4 sheets, copies = students x sheets.",
            1,
        )
    return text


def fix_database():
    import sys
    sys.path.insert(0, str(DEV))
    import paper_rates
    bak = DEV / "backups" / ("paper_bank_before_rates_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
    bak.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEV_DB, bak)
    con = sqlite3.connect(DEV_DB)
    try:
        paper_rates.ensure(con)
        con.execute(
            """CREATE TRIGGER IF NOT EXISTS block_old_online_paper
            BEFORE INSERT ON school_ledger
            WHEN NEW.detail LIKE 'Online paper %'
            BEGIN
                SELECT RAISE(IGNORE);
            END"""
        )
        info = [row[1] for row in con.execute("PRAGMA table_info(school_ledger)")]
        rows = list(con.execute("SELECT rowid, * FROM school_ledger"))
        hits = []
        for row in rows:
            data = dict(zip(info, row[1:]))
            detail = str(data.get("detail", ""))
            amount = int(data.get("amount") or 0)
            rate = int(data.get("rate") or 0)
            if "Online paper UKG MATH" in detail and amount == 400 and rate == 10:
                hits.append(row[0])
        if len(hits) != 1:
            raise SystemExit("ABORT LEDGER %s" % len(hits))
        con.execute("DELETE FROM school_ledger WHERE rowid=?", (hits[0],))
        docx = DEV / "production_jobs" / "PAPERS" / "BSM" / ("ACTUAL_" + PAPER_CODE + ".docx")
        sheets = paper_rates.sheets_in_docx(docx)
        detail = "Paper copies UKG MATH " + PAPER_CODE
        current = None
        for row in con.execute("SELECT rowid, * FROM school_ledger"):
            data = dict(zip(info, row[1:]))
            if data.get("school_code") == "BSM" and data.get("detail") == detail:
                current = (row[0], int(data.get("qty") or 0), int(data.get("rate") or 0), int(data.get("amount") or 0))
                break
        updated = "no"
        if current and sheets > 1 and current[1] == 40 and current[2] == 1 and current[3] == 40:
            billed = 40 * sheets
            con.execute(
                "UPDATE school_ledger SET qty=?, amount=?, detail=? WHERE rowid=?",
                (billed, billed, "Paper copies UKG MATH %s 40 students x %s sheets" % (PAPER_CODE, sheets), current[0]),
            )
            updated = "yes"
        con.commit()
        left = 0
        for row in con.execute("SELECT * FROM school_ledger"):
            data = dict(zip(info, row))
            if "Online paper UKG MATH" in str(data.get("detail", "")):
                left += 1
        print("DELETED_400", hits[0])
        print("SHEETS", sheets)
        print("OLD_COPY_UPDATED", updated)
        print("ONLINE_LEFT", left)
        print("db_backup=%s" % bak)
    finally:
        con.close()


def patch_companion_text():
    heading = "<h1>Central production queue</h1>"
    link = '<p><a href="/saini/paper-rates">Paper rates (SAINI)</a></p>'
    card = "Rate Rs 20 per card."
    card_new = "Rate Rs 20 per card. Paper rates are set by Saini for each school. If one paper needs 2, 3 or 4 sheets, copies = students x sheets."
    linked = "no"
    noted = "no"
    for path in sorted(DEV.glob("*.py")):
        if path.resolve() == APP.resolve() or "backup" in path.name.lower():
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8").replace("\r\n", "\n")
        changed = False
        if text.count(heading) == 1 and "/saini/paper-rates" not in text:
            text = text.replace(heading, heading + link, 1)
            changed = True
            linked = path.name
        if text.count(card) == 1:
            text = text.replace(card, card_new, 1)
            changed = True
            noted = path.name
        if not changed:
            continue
        if b"\r\n" in raw:
            text = text.replace("\n", "\r\n")
        backup = BACKUP_DIR / (path.stem + "_before_rates.py")
        stamp = 2
        while backup.exists():
            backup = BACKUP_DIR / ("%s_before_rates_%s.py" % (path.stem, stamp))
            stamp += 1
        backup.write_bytes(raw)
        path.write_bytes(text.encode("utf-8"))
        try:
            py_compile.compile(str(path), cfile=str(path.with_suffix(".rates_check.pyc")), doraise=True)
        except Exception as exc:
            path.write_bytes(raw)
            raise SystemExit("ABORT COMPANION %s %s" % (path.name, exc))
        finally:
            path.with_suffix(".rates_check.pyc").unlink(missing_ok=True)
    print("QUEUE_LINK", linked)
    print("ACCOUNT_NOTE", noted)


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    raw = APP.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    crlf = b"\r\n" in raw
    text = patch_bill(text)
    text = add_route(text)
    module = DEV / "paper_rates.py"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / "subject_wizard_dev_before_rates.py"
    stamp = 2
    while bak.exists():
        bak = BACKUP_DIR / ("subject_wizard_dev_before_rates_%s.py" % stamp)
        stamp += 1
    bak.write_bytes(raw)
    if module.exists():
        shutil.copy2(module, BACKUP_DIR / "paper_rates_before_rates.py")
    module.write_text(RATES, encoding="utf-8")
    if crlf:
        text = text.replace("\n", "\r\n")
    tmp = APP.with_name(APP.name + ".rates_tmp")
    chk = APP.with_name(APP.name + ".rates_check.pyc")
    try:
        tmp.write_bytes(text.encode("utf-8"))
        py_compile.compile(str(tmp), cfile=str(chk), doraise=True)
        py_compile.compile(str(module), cfile=str(DEV / "paper_rates.rates_check.pyc"), doraise=True)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        chk.unlink(missing_ok=True)
        (DEV / "paper_rates.rates_check.pyc").unlink(missing_ok=True)
    tmp.replace(APP)
    try:
        fix_database()
    except BaseException:
        APP.write_bytes(raw)
        raise
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        APP.write_bytes(raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    try:
        patch_companion_text()
    except SystemExit as exc:
        print(exc)
    print("PATCH_OK")
    print("rates_page=/saini/paper-rates")
    print("default_master=10")
    print("default_copy=1")
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("printer=not_started")


if __name__ == "__main__":
    main()
