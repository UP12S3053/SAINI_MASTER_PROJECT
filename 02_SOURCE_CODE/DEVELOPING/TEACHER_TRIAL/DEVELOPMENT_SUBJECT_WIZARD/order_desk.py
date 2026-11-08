# -*- coding: utf-8 -*-
"""One school order on the existing Saini Paper System.

Nursery to Class 2 stays on the paper setter. Class 3 to 12 stays on the old
project. The final file is chosen here and saved in the same archive folder.
Print Manager starts only when every line has a file. The bill is written
with the file. No separate command is part of the daily work.
"""
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

SETTER = ("NUR", "LKG", "UKG", "I", "II")
LEGACY = ("III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
ORDERED = SETTER + LEGACY
CLASS_NORM = {
    "NURSERY": "NUR", "NUR": "NUR", "LKG": "LKG", "UKG": "UKG",
    "1": "I", "I": "I", "2": "II", "II": "II",
    "3": "III", "III": "III", "4": "IV", "IV": "IV",
    "5": "V", "V": "V", "6": "VI", "VI": "VI",
    "7": "VII", "VII": "VII", "8": "VIII", "VIII": "VIII",
    "9": "IX", "IX": "IX", "10": "X", "X": "X",
    "11": "XI", "XI": "XI", "12": "XII", "XII": "XII",
}
SUBJECTS = ("MATH", "ENGLISH", "HINDI", "EVS", "SCIENCE", "SST", "COMPUTER", "GK")
SUBJECT_BIT = {
    "MATH": "MAT", "ENGLISH": "ENG", "HINDI": "HIN", "EVS": "EVS",
    "SCIENCE": "SCI", "SST": "SST", "COMPUTER": "COM", "GK": "GK",
}
PRINT_SCRIPT = Path(os.environ.get(
    "SAINI_PRINT_MANAGER",
    r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\PRINT_MANAGER.py",
))
PAPER_OUTPUT = Path(os.environ.get(
    "SAINI_PAPER_OUTPUT",
    r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\OUTPUT",
))


def root_of(folder):
    folder = Path(folder).resolve()
    if folder.name != "DEVELOPMENT_SUBJECT_WIZARD":
        raise RuntimeError("REFUSED: order desk writes only inside the development folder")
    return folder


def connect(folder):
    folder = root_of(folder)
    conn = sqlite3.connect(folder / "paper_bank.db", timeout=20)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _school(value):
    token = "".join(ch for ch in str(value or "").upper() if ch.isalnum())
    if not re.fullmatch(r"[A-Z0-9]{2,12}", token):
        raise ValueError("School code must be 2 to 12 letters")
    return token


def class_name(value):
    token = "".join(ch for ch in str(value or "").upper() if ch.isalnum())
    name = CLASS_NORM.get(token)
    if name not in SETTER and name not in LEGACY:
        raise ValueError("Class must be NUR to XII")
    return name


def subject_name(value):
    token = "".join(ch for ch in str(value or "").upper() if ch.isalpha())
    if token not in SUBJECTS:
        raise ValueError("Subject is not in the list")
    return token


def lane_for(name):
    return "setter" if name in SETTER else "legacy"


def _safe(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(str(name)).name)
    return cleaned[:120] or "paper.docx"


def ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS paper_order_lines (
            id INTEGER PRIMARY KEY,
            school_code TEXT NOT NULL,
            class_name TEXT NOT NULL,
            subject TEXT NOT NULL,
            students INTEGER NOT NULL,
            sheets INTEGER NOT NULL DEFAULT 1,
            lane TEXT NOT NULL,
            doc_code TEXT NOT NULL DEFAULT '',
            filename TEXT NOT NULL DEFAULT '',
            stored_path TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            UNIQUE (school_code, class_name, subject)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_ledger (
            id INTEGER PRIMARY KEY,
            school_code TEXT NOT NULL,
            job_code TEXT NOT NULL,
            detail TEXT NOT NULL,
            qty INTEGER NOT NULL,
            rate INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.commit()


def rates(conn, school):
    master, copy = 10, 1
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "school_paper_rates" not in names:
        return master, copy
    cols = {row[1] for row in conn.execute("PRAGMA table_info(school_paper_rates)")}
    if "master_rate" not in cols or "copy_rate" not in cols:
        return master, copy
    row = conn.execute(
        "SELECT master_rate, copy_rate FROM school_paper_rates WHERE school_code=?",
        (school,),
    ).fetchone()
    if row:
        return int(row[0]), int(row[1])
    return master, copy


def add_line(conn, school, klass, subject, students):
    school = _school(school)
    klass = class_name(klass)
    subject = subject_name(subject)
    count = int(students)
    if count < 1 or count > 500:
        raise ValueError("Students must be 1 to 500")
    ensure(conn)
    conn.execute(
        """INSERT INTO paper_order_lines
        (school_code, class_name, subject, students, sheets, lane, created_at)
        VALUES (?,?,?,?,1,?,?)
        ON CONFLICT(school_code, class_name, subject)
        DO UPDATE SET students=excluded.students""",
        (school, klass, subject, count, lane_for(klass), _now()),
    )
    conn.commit()


def sync_needs(conn, school):
    school = _school(school)
    ensure(conn)
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "school_paper_needs" not in names:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(school_paper_needs)")}
    if not {"class_name", "subject", "student_strength"} <= cols:
        return
    rows = conn.execute(
        """SELECT class_name, subject, student_strength FROM school_paper_needs
        WHERE school_code=?""",
        (school,),
    ).fetchall()
    for klass, subject, strength in rows:
        try:
            add_line(conn, school, klass, subject, int(strength or 0) or 1)
        except ValueError:
            continue


def _tokens(text):
    return {part for part in re.split(r"[^A-Z0-9]+", str(text or "").upper()) if part}


def _matches(line, code, filename):
    tokens = _tokens(code) | _tokens(filename)
    if line["class_name"] not in tokens:
        return False
    bit = SUBJECT_BIT.get(line["subject"], "")
    return line["subject"] in tokens or (bit and bit in tokens)


def sheets_in_docx(path):
    try:
        with zipfile.ZipFile(path) as book:
            xml = book.read("word/document.xml").decode("utf-8", "ignore")
    except (OSError, zipfile.BadZipFile, KeyError):
        return 0
    breaks = xml.count('w:type="page"') + xml.count("lastRenderedPageBreak")
    return breaks + 1 if breaks else 0


def _archive_rows(conn, school):
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "document_archive" not in names:
        return []
    return conn.execute(
        """SELECT code, filename, stored_path FROM document_archive
        WHERE school_code=? AND deleted=0 AND kind='paper'""",
        (school,),
    ).fetchall()



def _for_school(name, school):
    noise = set(ORDERED) | set(SUBJECTS) | set(SUBJECT_BIT.values()) | {
        "HM", "EM", "MEDIUM", "WORKSHEET", "PAPER", "ALL", "CHECK",
        "CLASS", "UNKNOWN", "SCHOOL", "DOCX", "PDF",
    }
    tokens = _tokens(name)
    if school in tokens:
        return True
    extra = [token for token in tokens if token.isalpha() and token not in noise and len(token) > 1]
    return not extra


def _output_files():
    if not PAPER_OUTPUT.is_dir():
        return []
    found = []
    for path in PAPER_OUTPUT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".docx", ".pdf"}:
            continue
        upper = path.name.upper()
        if "TEACHER_KEY" in upper or upper.startswith("DEMO_") or upper.endswith("_CHECK.DOCX"):
            continue
        if any(part.upper() in {"COMBINED_PDF", "BACKUPS"} for part in path.parts):
            continue
        found.append(path)
    found.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return found


def _take_generated(conn, folder, school, line, source):
    source = Path(source)
    detected = sheets_in_docx(source) if source.suffix.lower() == ".docx" else 0
    sheets = detected or int(line["sheets"] or 1)
    if sheets < 1 or sheets > 20:
        sheets = 1
    code = re.sub(r"[^A-Z0-9-]+", "-", source.stem.upper())[:80].strip("-") or "PAPER"
    target_dir = folder / "production_jobs" / "PAPERS" / school
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _safe(code + source.suffix.lower())
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        target.write_bytes(source.read_bytes())
    try:
        import document_archive
        document_archive.keep(folder, school, "paper", code, target)
    except Exception:
        pass
    master_amount, copy_amount = _bill(
        conn, school, line["class_name"], line["subject"], code, int(line["students"]), sheets,
    )
    conn.execute(
        """UPDATE paper_order_lines
        SET sheets=?, doc_code=?, filename=?, stored_path=? WHERE id=?""",
        (sheets, code, target.name, str(target), line["id"]),
    )
    conn.commit()
    return master_amount + copy_amount


def pull_generated(conn, folder, school):
    folder = root_of(folder)
    school = _school(school)
    ensure(conn)
    waiting = []
    for line in lines_for(conn, school):
        if line["lane"] != "legacy":
            continue
        if line["stored_path"] and Path(line["stored_path"]).is_file():
            continue
        waiting.append(line)
    placed = 0
    for source in _output_files():
        if not waiting:
            break
        for line in list(waiting):
            if not _matches(line, source.stem, source.name) or not _for_school(source.name, school):
                continue
            _take_generated(conn, folder, school, line, source)
            waiting.remove(line)
            placed += 1
            break
    return placed


def accept_generated(source):
    folder = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD")
    if not Path(source).is_file() or not folder.is_dir():
        return 0
    conn = connect(folder)
    try:
        schools = [row[0] for row in conn.execute("SELECT DISTINCT school_code FROM paper_order_lines")]
        total = 0
        for school in schools or ["BSM"]:
            total += pull_generated(conn, folder, school)
        return total
    finally:
        conn.close()

def link_saved(conn, folder, school):
    folder = root_of(folder)
    school = _school(school)
    ensure(conn)
    rows = conn.execute(
        """SELECT * FROM paper_order_lines
        WHERE school_code=? ORDER BY id""",
        (school,),
    ).fetchall()
    found = list(_archive_rows(conn, school))
    papers = folder / "production_jobs" / "PAPERS" / school
    if papers.is_dir():
        for path in papers.iterdir():
            if path.is_file() and path.suffix.lower() in {".docx", ".pdf"}:
                found.append({"code": path.stem, "filename": path.name, "stored_path": str(path)})
    for line in rows:
        if line["stored_path"] and Path(line["stored_path"]).is_file():
            continue
        for item in found:
            if not _matches(line, item["code"], item["filename"]):
                continue
            path = Path(item["stored_path"])
            if not path.is_file():
                path = folder / item["stored_path"]
            if not path.is_file():
                continue
            conn.execute(
                """UPDATE paper_order_lines
                SET doc_code=?, filename=?, stored_path=? WHERE id=?""",
                (str(item["code"])[:80], path.name, str(path), line["id"]),
            )
            break
    conn.commit()


def lines_for(conn, school):
    ensure(conn)
    return conn.execute(
        "SELECT * FROM paper_order_lines WHERE school_code=? ORDER BY id",
        (_school(school),),
    ).fetchall()


def ready(rows):
    return len(rows) > 0 and all(row["stored_path"] and Path(row["stored_path"]).is_file() for row in rows)


def _bill(conn, school, klass, subject, code, students, sheets):
    master_rate, copy_rate = rates(conn, school)
    stamp = _now()
    master = "Paper master %s %s" % (klass, subject)
    if conn.execute(
        "SELECT 1 FROM school_ledger WHERE school_code=? AND detail=? LIMIT 1",
        (school, master),
    ).fetchone() is None:
        conn.execute(
            """INSERT INTO school_ledger
            (school_code, job_code, detail, qty, rate, amount, created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (school, code, master, 1, master_rate, master_rate, stamp),
        )
    detail = "Paper copies %s %s %s %d students x %d sheets" % (klass, subject, code, students, sheets)
    qty = students * sheets
    if conn.execute(
        "SELECT 1 FROM school_ledger WHERE school_code=? AND detail=? LIMIT 1",
        (school, detail),
    ).fetchone() is None:
        conn.execute(
            """INSERT INTO school_ledger
            (school_code, job_code, detail, qty, rate, amount, created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (school, code, detail, qty, copy_rate, qty * copy_rate, stamp),
        )
    return master_rate, qty * copy_rate


def save_final(conn, folder, school, line_id, source, sheets_choice):
    folder = root_of(folder)
    school = _school(school)
    ensure(conn)
    line = conn.execute(
        "SELECT * FROM paper_order_lines WHERE id=? AND school_code=?",
        (int(line_id), school),
    ).fetchone()
    if line is None:
        raise ValueError("That line is not in this school order")
    if line["lane"] != "legacy":
        raise ValueError("Nursery to Class 2 is made in the paper setter")
    if line["stored_path"]:
        raise ValueError("This class is already in the folder")
    source = Path(source)
    if source.suffix.lower() not in {".docx", ".pdf"} or not source.is_file():
        raise ValueError("Choose a docx or pdf final file")
    if source.name.upper().startswith("DEMO_"):
        raise ValueError("Demo files are not saved")
    raw = source.read_bytes()
    day = datetime.now().strftime("%Y%m%d")
    bit = SUBJECT_BIT[line["subject"]]
    tail = hashlib.sha256(raw).hexdigest()[:4].upper()
    code = "%s-%s-%s-%s-%s" % (school, line["class_name"], bit, day, tail)
    target_dir = folder / "production_jobs" / "PAPERS" / school
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / _safe(code + source.suffix.lower())
    target.write_bytes(raw)
    detected = sheets_in_docx(target) if target.suffix.lower() == ".docx" else 0
    sheets = detected or int(sheets_choice or line["sheets"] or 1)
    if sheets < 1 or sheets > 20:
        raise ValueError("Sheets must be 1 to 20")
    try:
        import document_archive
        document_archive.keep(folder, school, "paper", code, target)
    except Exception:
        pass
    master_amount, copy_amount = _bill(
        conn, school, line["class_name"], line["subject"], code, int(line["students"]), sheets,
    )
    conn.execute(
        """UPDATE paper_order_lines
        SET sheets=?, doc_code=?, filename=?, stored_path=? WHERE id=?""",
        (sheets, code, target.name, str(target), line["id"]),
    )
    conn.commit()
    return {"code": code, "sheets": sheets, "master": master_amount, "copies": copy_amount}


def _xml(value):
    amp = chr(38) + "amp;"
    lt = chr(38) + "lt;"
    gt = chr(38) + "gt;"
    return str(value).replace(chr(38), amp).replace("<", lt).replace(">", gt)


def _column(number):
    letters = ""
    while number:
        number, rest = divmod(number - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def write_xlsx(path, rows):
    sheet_rows = []
    for r_index, row in enumerate(rows, start=1):
        cells = []
        for c_index, value in enumerate(row, start=1):
            ref = "%s%d" % (_column(c_index), r_index)
            if isinstance(value, int):
                cells.append('<c r="%s"><v>%d</v></c>' % (ref, value))
            else:
                cells.append(
                    '<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (ref, _xml(value))
                )
        sheet_rows.append('<row r="%d">%s</row>' % (r_index, "".join(cells)))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>%s</sheetData></worksheet>' % "".join(sheet_rows)
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        book.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        book.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        book.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="PAPER" sheetId="1" r:id="rId1"/></sheets></workbook>""")
        book.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""")
        book.writestr("xl/worksheets/sheet1.xml", sheet)
    return path


def build_excel(conn, folder, school):
    folder = root_of(folder)
    school = _school(school)
    rows = lines_for(conn, school)
    if not ready(rows):
        missing = ["%s %s" % (row["class_name"], row["subject"]) for row in rows if not row["stored_path"]]
        raise ValueError("Print closed. Missing: " + ", ".join(missing or ["no lines"]))
    table = [[
        "SCHOOL NAME", "CLASS", "SUBJECT", "STUDENTS", "SHEETS_PER_COPY",
        "SOURCE_FILE", "MEDIUM", "LAYOUT",
    ]]
    for row in rows:
        name = row["filename"].upper()
        medium = "HINDI_MEDIUM" if "_HM" in name or "-HM" in name else ""
        if "_EM" in name or "-EM" in name:
            medium = "ENGLISH_MEDIUM"
        table.append([
            school, row["class_name"], row["subject"], int(row["students"]), int(row["sheets"] or 1),
            row["stored_path"], medium, "2-UP",
        ])
    target = folder / "production_jobs" / "PAPERS" / school / "PAPER_PRINT.xlsx"
    write_xlsx(target, table)
    official = PRINT_SCRIPT.parent / "PRINT.xlsx"
    write_xlsx(official, table)
    return official


def start_print(excel, script=None):
    script = Path(script or PRINT_SCRIPT)
    excel = Path(excel)
    if not excel.is_file():
        raise ValueError("Print sheet was not written")
    if not script.is_file():
        raise ValueError("Print Manager was not found at " + str(script))
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        [sys.executable, str(script), "--excel", str(excel), "--print"],
        cwd=str(script.parent),
        creationflags=flags,
    )
    return "Print Manager started for " + excel.name


def bill_total(conn, school):
    ensure(conn)
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM school_ledger WHERE school_code=? AND detail LIKE 'Paper %'",
        (_school(school),),
    ).fetchone()
    return int(row[0])


def _esc(value):
    return _xml(value)


def render(school, rows, can_print, notice, token, amount):
    done = sum(1 for row in rows if row["stored_path"])
    body = []
    for row in rows:
        saved = bool(row["stored_path"])
        if saved:
            action = "In folder · %s · %d sheet(s)" % (_esc(row["filename"]), int(row["sheets"] or 1))
        elif row["lane"] == "setter":
            action = '<a href="/paper?class_level=%s&subject=%s">Open paper setter</a>' % (
                _esc(row["class_name"]), _esc(row["subject"]),
            )
        else:
            action = "PAPER.py saves this file here. No file to choose."
        body.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%d</td><td>%s</td><td>%s</td></tr>"
            % (
                _esc(row["class_name"]), _esc(row["subject"]),
                "Paper setter" if row["lane"] == "setter" else "Old project 3-12",
                int(row["students"]), "In folder" if saved else "Waiting", action,
            )
        )
    if can_print and ready(rows):
        print_block = (
            '<form method="post"><input type="hidden" name="csrf" value="%s">'
            '<input type="hidden" name="action" value="print">'
            '<button class="go" type="submit">Make PRINT.xlsx and print</button></form>'
        ) % token
    elif can_print:
        print_block = "<p>Print stays closed until every class file is in the folder.</p>"
    else:
        print_block = "<p>Printing stays on the Saini page. This page can make and save files.</p>"
    classes = "".join("<option>%s</option>" % name for name in ORDERED)
    subjects = "".join("<option>%s</option>" % name for name in SUBJECTS)
    return """<!doctype html><html><head><meta charset="utf-8"><title>Complete paper order</title>
<style>
body{font-family:Arial;margin:0;background:#f4f7fb;color:#172033}
main{max-width:980px;margin:24px auto;background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}
a.go,button.go{display:block;background:#1f9d55;color:white;text-align:center;text-decoration:none;border:0;border-radius:8px;padding:14px;font-size:16px;width:100%%;margin:8px 0}
table{width:100%%;border-collapse:collapse}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px;vertical-align:top}
input,select,button{font:16px Arial;padding:8px;margin:4px 4px 4px 0}
.note{background:#e8f6ee;padding:10px;border-radius:8px}
</style></head><body><main>
<p><a href="/">Home</a></p>
<h1>Complete paper order</h1>
<p>School %s. Nursery to Class 2 uses the paper setter. Class 3 to 12 is made by PAPER.py and the file comes here by itself.</p>
<p class="note">%d of %d files are in the folder. Paper bill so far: Rs %d. %s</p>
<table><tr><th>Class</th><th>Subject</th><th>Lane</th><th>Students</th><th>File</th><th></th></tr>%s</table>
<h2>Add a class</h2>
<form method="post">
<input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="add">
<select name="class_name">%s</select>
<select name="subject">%s</select>
<input name="students" inputmode="numeric" value="30" size="6" required>
<button type="submit">Add to order</button>
</form>
%s
</main></body></html>""" % (
        _esc(school), done, len(rows), amount, _esc(notice),
        "".join(body), token, classes, subjects, print_block,
    )


def render_page(conn, school, rows, can_print, notice, token):
    return render(school, rows, can_print, notice, token, bill_total(conn, school))


def handle(conn, folder, school, form, files, can_print):
    action = (form.get("action") or "").strip()
    if action == "add":
        add_line(conn, school, form.get("class_name"), form.get("subject"), form.get("students") or "0")
        return "Added %s %s." % (class_name(form.get("class_name")), subject_name(form.get("subject")))
    if action == "save":
        upload = files.get("final_file")
        if upload is None or not getattr(upload, "filename", ""):
            raise ValueError("Choose the final file")
        import tempfile
        suffix = Path(upload.filename).suffix.lower()
        handle_temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        handle_temp.close()
        upload.save(handle_temp.name)
        try:
            saved = save_final(conn, folder, school, form.get("line_id"), handle_temp.name, form.get("sheets") or "")
        finally:
            Path(handle_temp.name).unlink(missing_ok=True)
        return "Saved %s. Master Rs %d. Copies Rs %d." % (saved["code"], saved["master"], saved["copies"])
    if action == "print":
        if not can_print:
            raise ValueError("Only Saini can start printing")
        excel = build_excel(conn, folder, school)
        return start_print(excel)
    raise ValueError("Unknown action")


def attach(app):
    if "saini_order" in getattr(app, "view_functions", {}):
        return

    def _folder():
        return root_of(Path(app.root_path))

    def _csrf(session):
        import secrets
        token = session.get("order_csrf")
        if not token:
            token = secrets.token_hex(16)
            session["order_csrf"] = token
        return token

    def _posted(request, session):
        import hmac
        sent = request.form.get("csrf") or ""
        stored = session.get("order_csrf") or ""
        if not stored or not hmac.compare_digest(sent, stored):
            raise ValueError("Reload the page and try again")

    @app.route("/portal/order", methods=["GET", "POST"])
    def portal_order():
        from flask import redirect, request, session
        school = session.get("portal_school")
        if not school:
            return redirect("/school-login?next=/portal/order")
        return _show(_folder(), school, request, session, False)

    @app.route("/saini/order", methods=["GET", "POST"])
    def saini_order():
        from flask import redirect, request, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/saini/order"))
        school = request.values.get("school") or "BSM"
        try:
            school = _school(school)
        except ValueError:
            school = "BSM"
        return _show(_folder(), school, request, session, True)

    def _show(folder, school, request, session, can_print):
        notice = ""
        conn = connect(folder)
        try:
            if request.method == "POST":
                try:
                    _posted(request, session)
                    notice = handle(conn, folder, school, request.form, request.files, can_print)
                except Exception as error:
                    notice = str(error)
            sync_needs(conn, school)
            pull_generated(conn, folder, school)
            link_saved(conn, folder, school)
            rows = lines_for(conn, school)
            page = render_page(conn, school, rows, can_print, notice, _csrf(session))
        finally:
            conn.close()
        return page
