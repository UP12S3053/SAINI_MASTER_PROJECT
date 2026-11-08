# -*- coding: utf-8 -*-
"""Add ID card, tie, belt and copy/diary rates to the Saini rate page."""
import hashlib
import py_compile
import re
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
DEV = APP.parent
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")

RATES = r'''# -*- coding: utf-8 -*-
"""Prices belong to Saini. A school cannot change its own rate."""
import struct
import zipfile
from pathlib import Path

FIELDS = (
    ("master_rate", 10),
    ("copy_rate", 1),
    ("id_card_rate", 20),
    ("tie_small_rate", 0),
    ("tie_big_rate", 0),
    ("belt_rate", 0),
    ("diary_rate", 0),
)


def ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_paper_rates (
            school_code TEXT PRIMARY KEY,
            master_rate INTEGER NOT NULL,
            copy_rate INTEGER NOT NULL
        )"""
    )
    have = {row[1] for row in conn.execute("PRAGMA table_info(school_paper_rates)")}
    for name, default in FIELDS:
        if name not in have:
            conn.execute(
                "ALTER TABLE school_paper_rates ADD COLUMN %s INTEGER NOT NULL DEFAULT %d" % (name, default)
            )
    conn.commit()


def _clean(school_code):
    code = (school_code or "").strip().upper()
    if not code or len(code) > 20:
        raise ValueError("School code is required")
    return code


def _number(value, label):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(label + " must be a whole number")
    if number < 0 or number > 500:
        raise ValueError(label + " must be from 0 to 500")
    return number


def all_rates(conn, school_code):
    ensure(conn)
    code = (school_code or "").strip().upper()
    row = conn.execute(
        "SELECT " + ",".join(name for name, _default in FIELDS) + " FROM school_paper_rates WHERE school_code=?",
        (code,),
    ).fetchone()
    if row is None:
        return {name: default for name, default in FIELDS}
    return {name: int(row[index]) for index, (name, _default) in enumerate(FIELDS)}


def rates_for(conn, school_code):
    data = all_rates(conn, school_code)
    return data["master_rate"], data["copy_rate"]


def item_rate(conn, school_code, item):
    data = all_rates(conn, school_code)
    key = item if item in data else item + "_rate"
    if key not in data:
        raise ValueError("Unknown rate")
    return data[key]


def set_rates(conn, school_code, values):
    ensure(conn)
    code = _clean(school_code)
    saved = {name: _number(values[name], name) for name, _default in FIELDS}
    columns = ["school_code"] + [name for name, _default in FIELDS]
    holders = ",".join("?" for _ in columns)
    updates = ",".join(name + "=excluded." + name for name, _default in FIELDS)
    conn.execute(
        "INSERT INTO school_paper_rates (" + ",".join(columns) + ") VALUES (" + holders + ") "
        "ON CONFLICT(school_code) DO UPDATE SET " + updates,
        [code] + [saved[name] for name, _default in FIELDS],
    )
    conn.commit()
    return code


def list_rates(conn):
    ensure(conn)
    return list(conn.execute(
        "SELECT school_code," + ",".join(name for name, _default in FIELDS) + " FROM school_paper_rates ORDER BY school_code"
    ))


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

ROUTE = r'''@app.route("/saini/paper-rates", methods=["GET", "POST"])
def saini_paper_rates():
    import paper_rates
    if not session.get("saini_teacher_authenticated"):
        return redirect(url_for("trial_login", next="/saini/paper-rates"))
    conn = get_db()
    message = ""
    error = ""
    if request.method == "POST":
        try:
            code = paper_rates.set_rates(conn, request.form.get("school_code", ""), {
                "master_rate": request.form.get("master_rate", ""),
                "copy_rate": request.form.get("copy_rate", ""),
                "id_card_rate": request.form.get("id_card_rate", ""),
                "tie_small_rate": request.form.get("tie_small_rate", ""),
                "tie_big_rate": request.form.get("tie_big_rate", ""),
                "belt_rate": request.form.get("belt_rate", ""),
                "diary_rate": request.form.get("diary_rate", ""),
            })
            message = "Saved " + code + ". The next job uses these rates."
        except (TypeError, ValueError) as exc:
            error = str(exc)
    rows = paper_rates.list_rates(conn)
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % tuple(row)
        for row in rows
    )
    flag = ""
    if error:
        flag += '<p class="bad">%s</p>' % error
    if message:
        flag += '<p class="ok">%s</p>' % message
    fields = (
        ("master_rate", "Paper master", "10"),
        ("copy_rate", "Paper copy", "1"),
        ("id_card_rate", "ID card", "20"),
        ("tie_small_rate", "Medium / small tie", "0"),
        ("tie_big_rate", "Big tie", "0"),
        ("belt_rate", "Belt", "0"),
        ("diary_rate", "Copy / diary", "0"),
    )
    inputs = "".join(
        '<label>%s</label><input name="%s" value="%s" inputmode="numeric" required>' % (label, name, value)
        for name, label, value in fields
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Paper rates</title>'
        '<style>body{font-family:Arial;max-width:980px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}'
        'main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}'
        'label{display:block;font-weight:bold;margin-top:12px}input,button{box-sizing:border-box;width:100%;padding:11px;margin-top:6px;font-size:16px}'
        'button{background:#17365d;color:white;border:0;border-radius:8px;width:auto;padding:11px 18px}'
        'table{width:100%;border-collapse:collapse;margin-top:16px;font-size:14px}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px}'
        '.ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}</style></head><body><main>'
        '<p><a href="/">Home</a></p><h1>School rates</h1>'
        '<p>Only Saini can change a rate. A school cannot. Blank school means paper master Rs 10, paper copy Rs 1, ID card Rs 20. Tie, belt and copy/diary stay 0 until you save them. 0 means no charge yet.</p>'
        + flag
        + '<form method="post"><label>School code</label><input name="school_code" required maxlength="20">'
        + inputs
        + '<button type="submit">Save rate</button></form>'
        '<table><tr><th>School</th><th>Master</th><th>Paper copy</th><th>ID card</th><th>Small tie</th><th>Big tie</th><th>Belt</th><th>Copy/diary</th></tr>'
        + body + '</table></main></body></html>'
    )
'''


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_route(text):
    start = text.find('@app.route("/saini/paper-rates"')
    if start < 0 or text.count('@app.route("/saini/paper-rates"') != 1:
        raise SystemExit("ABORT ROUTE")
    marker = '\nif __name__ == "__main__":'
    end = text.find(marker, start)
    if end < 0:
        raise SystemExit("ABORT MAIN")
    chunk = text[start:end]
    if chunk.count("\ndef ") != 1:
        raise SystemExit("ABORT ROUTE_BODY")
    return text[:start] + ROUTE.strip() + "\n" + text[end + 1:]


def hook_id_card():
    pattern = re.compile(
        r"\((?P<school>\w+),\s*(?P<job>[^,]+),\s*(?P<detail>[^,]+),\s*(?P<qty>\w+),\s*20,\s*(?P=qty)\s*\*\s*20,"
    )
    hits = []
    for path in sorted(DEV.glob("*.py")):
        if "backup" in path.name.lower() or path.name.startswith("patch_"):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if not pattern.search(line):
                continue
            window = "\n".join(lines[max(0, index - 25):index + 1]).lower()
            if "card" not in window:
                continue
            hits.append((path, index, line))
    if len(hits) != 1:
        print("ID_HOOK", "skipped", len(hits))
        for path, index, line in hits[:8]:
            print("ID_LINE", path.name, index + 1, line.strip()[:180])
        return
    path, index, line = hits[0]
    match = pattern.search(line)
    raw = path.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    replacement = "(%s, %s, %s, %s, paper_rates.item_rate(%s, %s, 'id_card'), %s * paper_rates.item_rate(%s, %s, 'id_card')," % (
        match.group("school"), match.group("job").strip(), match.group("detail").strip(), match.group("qty"),
        "conn", match.group("school"), match.group("qty"), "conn", match.group("school"),
    )
    # The connection name is corrected below from the nearest .execute.
    lines = text.splitlines()
    current = lines[index]
    found = pattern.search(current)
    conn_name = "conn"
    for earlier in range(index, max(-1, index - 8), -1):
        execute = re.search(r"(\w+)\.execute\(", lines[earlier])
        if execute:
            conn_name = execute.group(1)
            break
    replacement = "(%s, %s, %s, %s, paper_rates.item_rate(%s, %s, 'id_card'), %s * paper_rates.item_rate(%s, %s, 'id_card')," % (
        found.group("school"), found.group("job").strip(), found.group("detail").strip(), found.group("qty"),
        conn_name, found.group("school"), found.group("qty"), conn_name, found.group("school"),
    )
    lines[index] = pattern.sub(replacement, current, count=1)
    if "import paper_rates" not in text:
        inserted = False
        for at, row in enumerate(lines):
            if row.startswith("import ") or row.startswith("from "):
                continue
            lines.insert(at, "import paper_rates")
            inserted = True
            break
        if not inserted:
            lines.insert(0, "import paper_rates")
    updated = "\n".join(lines)
    if b"\r\n" in raw:
        updated = updated.replace("\n", "\r\n")
    backup = BACKUP_DIR / (path.stem + "_before_more_rates.py")
    stamp = 2
    while backup.exists():
        backup = BACKUP_DIR / ("%s_before_more_rates_%s.py" % (path.stem, stamp))
        stamp += 1
    backup.write_bytes(raw)
    path.write_bytes(updated.encode("utf-8"))
    try:
        py_compile.compile(str(path), cfile=str(path.with_suffix(".more_check.pyc")), doraise=True)
    except Exception as exc:
        path.write_bytes(raw)
        print("ID_HOOK", "reverted", exc)
        return
    finally:
        path.with_suffix(".more_check.pyc").unlink(missing_ok=True)
    print("ID_HOOK", path.name, index + 1)


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    module = DEV / "paper_rates.py"
    if not module.is_file() or not APP.is_file():
        raise SystemExit("ABORT MISSING")
    raw = APP.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    text = replace_route(text)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / "subject_wizard_dev_before_more_rates.py"
    stamp = 2
    while bak.exists():
        bak = BACKUP_DIR / ("subject_wizard_dev_before_more_rates_%s.py" % stamp)
        stamp += 1
    bak.write_bytes(raw)
    shutil.copy2(module, BACKUP_DIR / ("paper_rates_before_more_rates_%s.py" % datetime.now().strftime("%H%M%S")))
    module.write_text(RATES, encoding="utf-8")
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    tmp = APP.with_name(APP.name + ".more_tmp")
    chk = APP.with_name(APP.name + ".more_check.pyc")
    try:
        tmp.write_bytes(text.encode("utf-8"))
        py_compile.compile(str(tmp), cfile=str(chk), doraise=True)
        py_compile.compile(str(module), cfile=str(DEV / "paper_rates.more_check.pyc"), doraise=True)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        chk.unlink(missing_ok=True)
        (DEV / "paper_rates.more_check.pyc").unlink(missing_ok=True)
    tmp.replace(APP)
    try:
        hook_id_card()
    except Exception as exc:
        print("ID_HOOK", "error", exc)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        APP.write_bytes(raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("PATCH_OK")
    print("fields=master,paper_copy,id_card,small_tie,big_tie,belt,diary")
    print("id_default=20")
    print("tie_belt_diary_default=0")
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))


if __name__ == "__main__":
    main()
