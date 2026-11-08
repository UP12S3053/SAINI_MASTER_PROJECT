# -*- coding: utf-8 -*-
"""Copy final papers and ID A4 sheets into one cross-check folder.

School can open the folder. Only Saini can delete a copy.
The print file itself is not deleted.
"""
import hashlib
import py_compile
import shutil
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
DEV = APP.parent
DATA = DEV / "school_data.py"
ORIG = Path(r"D:\SAINI_TEACHER_TRIAL\app_phase2_shortlisting_v2_trial_secure.py")
ORIG_DB = Path(r"D:\SAINI_TEACHER_TRIAL\paper_bank.db")
ORIG_APP_HASH = "53d03fad9d5b3dfa2a96b8faecf12611fa89589ef1b2c77eabd6949b55fc9180"
ORIG_DB_HASH = "f7b64b7924c87851a8dede0ede59b063c29c02ae26ac3049dd34b928b8c8363f"
BACKUP_DIR = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")

MODULE = r'''# -*- coding: utf-8 -*-
"""One cross-check folder. A school can view. Only Saini can delete."""
import hashlib
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

SCAN_SUFFIXES = {".docx", ".pdf"}
KEEP_SUFFIXES = {".docx", ".pdf", ".html"}


def _db(root):
    return Path(root) / "paper_bank.db"


def _connect(root):
    conn = sqlite3.connect(_db(root), timeout=20)
    conn.row_factory = sqlite3.Row
    row = conn.execute("PRAGMA database_list").fetchone()
    if Path(row[2]).resolve().parent.name != "DEVELOPMENT_SUBJECT_WIZARD":
        conn.close()
        raise RuntimeError("REFUSED: archive can write only the development database")
    return conn


def ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS document_archive (
            id INTEGER PRIMARY KEY,
            school_code TEXT NOT NULL,
            kind TEXT NOT NULL,
            code TEXT NOT NULL,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS document_archive_hash ON document_archive(sha256)"
    )
    conn.commit()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _school(value):
    token = "".join(ch for ch in str(value or "").upper() if ch.isalnum())
    return token[:20] or "UNKNOWN"


def _esc(value):
    text = str(value or "")
    amp = chr(38)
    text = text.replace(amp, amp + "amp;")
    text = text.replace(chr(60), amp + "lt;")
    text = text.replace(chr(62), amp + "gt;")
    text = text.replace(chr(34), amp + "quot;")
    return text


def code_from(name):
    stem = Path(name).stem
    if stem.upper().startswith("ACTUAL_"):
        stem = stem[7:]
    return stem[:80]


def school_from_filename(name):
    token = re.split(r"[-_]", code_from(name), maxsplit=1)[0]
    return _school(token)


def school_from_pdf(path):
    raw = Path(path).read_bytes()
    prefixes = set()
    for item in re.findall(br"[A-Z][A-Z0-9]{1,11}-\d{4}", raw):
        prefixes.add(item.decode("ascii").split("-")[0])
    if len(prefixes) == 1:
        return _school(next(iter(prefixes)))
    return "MULTI"


def _safe_name(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name)
    return cleaned[:120] or "document"


def keep(root, school, kind, code, source):
    source = Path(source)
    if not source.is_file() or source.suffix.lower() not in KEEP_SUFFIXES:
        return None
    if "document_archive" in {part.lower() for part in source.parts}:
        return None
    root = Path(root)
    conn = _connect(root)
    try:
        ensure(conn)
        digest = _sha(source)
        existing = conn.execute(
            "SELECT id, deleted FROM document_archive WHERE sha256=?",
            (digest,),
        ).fetchone()
        if existing:
            return None if existing["deleted"] else existing["id"]
        school_code = _school(school)
        folder = root / "document_archive" / school_code
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / _safe_name(source.name)
        if target.exists() and _sha(target) != digest:
            target = folder / (digest[:8] + "_" + _safe_name(source.name))
        if not target.exists():
            shutil.copy2(source, target)
        rel = target.relative_to(root).as_posix()
        cur = conn.execute(
            """INSERT INTO document_archive
            (school_code, kind, code, filename, stored_path, sha256, created_at, deleted)
            VALUES (?,?,?,?,?,?,?,0)""",
            (
                school_code, kind, str(code)[:80], target.name, rel, digest,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _wanted(path):
    path = Path(path)
    if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
        return False
    if path.name.upper().startswith("DEMO_"):
        return False
    parts = {part.lower() for part in path.parts}
    if "document_archive" in parts or "backups" in parts or "_deleted" in parts:
        return False
    return True


def _kind(path):
    stem = Path(path).stem.upper()
    if stem.startswith("ACTUAL_") or stem.startswith("DEMO_"):
        return "paper"
    return "idcard"


def snapshot_cards(root):
    root = Path(root)
    conn = _connect(root)
    made = 0
    try:
        ensure(conn)
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "school_delivery_orders" not in names or "school_delivery_slots" not in names:
            return 0
        orders = conn.execute(
            """SELECT id, school_code, job_code FROM school_delivery_orders
            WHERE want_cards=1 AND job_code!='' ORDER BY id"""
        ).fetchall()
        pending = []
        for order_id, school, job in orders:
            slots = conn.execute(
                """SELECT position, student_uid, student_name, class_name
                FROM school_delivery_slots WHERE order_id=? ORDER BY position""",
                (order_id,),
            ).fetchall()
            pending.append((school, job, slots))
    finally:
        conn.close()
    for school, job, slots in pending:
        cards = []
        for position, uid, name, klass in slots:
            cards.append(
                "<article><b>" + _esc(name) + "</b><br>" + _esc(uid) + "<br>"
                + _esc(klass) + "<br>Place " + str(int(position)) + "</article>"
            )
        if not cards:
            cards.append("<article>No students saved on this job</article>")
        sheets = []
        for index in range(0, len(cards), 10):
            sheets.append(
                "<section><h2>A4 sheet " + str(index // 10 + 1) + "</h2><div class=\"grid\">"
                + "".join(cards[index:index + 10]) + "</div></section>"
            )
        html = (
            "<!doctype html><meta charset=\"utf-8\"><title>" + _esc(job)
            + "</title><style>body{font-family:Arial;color:#172033}"
            ".grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}"
            "article{border:1px solid #17365d;padding:8px}"
            "section{page-break-after:always}</style><h1>"
            + _esc(school) + " " + _esc(job)
            + "</h1><p>ID card A4 cross-check. 10 cards on one sheet.</p>"
            + "".join(sheets)
        )
        folder = Path(tempfile.mkdtemp())
        path = folder / _safe_name(str(job) + ".html")
        path.write_text(html, encoding="utf-8")
        try:
            if keep(root, school, "idcard", job, path):
                made += 1
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return made


def scan(root):
    root = Path(root)
    snapshot_cards(root)
    papers = root / "production_jobs" / "PAPERS"
    if papers.is_dir():
        for path in papers.rglob("*"):
            if _wanted(path):
                school = path.parent.name if path.parent.name.upper() != "PAPERS" else school_from_filename(path.name)
                keep(root, school, "paper", code_from(path.name), path)
    jobs = root / "production_jobs"
    if jobs.is_dir():
        for path in jobs.rglob("*"):
            if _wanted(path) and "PAPERS" not in path.parts:
                keep(root, school_from_filename(path.name), _kind(path), code_from(path.name), path)
    output = root / "output_shortlisting_v2"
    if output.is_dir():
        for path in output.glob("*"):
            if _wanted(path):
                keep(root, school_from_filename(path.name), "paper", code_from(path.name), path)
    batches = root / "print_batches"
    if batches.is_dir():
        for path in batches.glob("*.pdf"):
            if _wanted(path):
                keep(root, school_from_pdf(path), "idcard", path.stem, path)
    return len(visible(root))


def visible(root, school_code=None):
    conn = _connect(root)
    try:
        ensure(conn)
        if school_code:
            rows = conn.execute(
                """SELECT id, school_code, kind, code, filename, created_at
                FROM document_archive WHERE deleted=0 AND school_code=? ORDER BY id DESC""",
                (_school(school_code),),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, school_code, kind, code, filename, created_at
                FROM document_archive WHERE deleted=0 ORDER BY id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def file_for(root, doc_id, school_code=None):
    root = Path(root)
    try:
        doc_id = int(doc_id)
    except (TypeError, ValueError):
        return None
    conn = _connect(root)
    try:
        ensure(conn)
        row = conn.execute(
            "SELECT school_code, stored_path, deleted FROM document_archive WHERE id=?",
            (doc_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or row["deleted"]:
        return None
    if school_code and row["school_code"] != _school(school_code):
        return None
    base = (root / "document_archive").resolve()
    path = (root / row["stored_path"]).resolve()
    if base not in path.parents or not path.is_file() or "_deleted" in path.parts:
        return None
    return path


def remove(root, doc_id):
    root = Path(root)
    try:
        doc_id = int(doc_id)
    except (TypeError, ValueError):
        return False
    conn = _connect(root)
    try:
        ensure(conn)
        row = conn.execute(
            "SELECT id, stored_path, deleted FROM document_archive WHERE id=?",
            (doc_id,),
        ).fetchone()
        if row is None or row["deleted"]:
            return False
        base = (root / "document_archive").resolve()
        path = (root / row["stored_path"]).resolve()
        if base not in path.parents:
            raise RuntimeError("REFUSED")
        if path.is_file():
            trash = base / "_deleted"
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(trash / ("%s_%s" % (row["id"], path.name))))
        conn.execute("UPDATE document_archive SET deleted=1 WHERE id=?", (row["id"],))
        conn.commit()
        return True
    finally:
        conn.close()
'''

ROUTES = r'''
def _archive_page(title, rows, can_delete):
    body = []
    labels = {"paper": "Paper", "idcard": "ID A4"}
    for row in rows:
        open_href = "/saini/archive-file" if can_delete else "/portal/archive-file"
        open_link = '<a href="%s?id=%s">Open</a>' % (open_href, int(row["id"]))
        delete_cell = ""
        if can_delete:
            delete_cell = (
                '<form method="post" style="margin:0" onsubmit="return confirm(\'Delete this cross-check copy?\')">'
                '<input type="hidden" name="doc_id" value="%s">'
                '<button type="submit">Delete</button></form>' % int(row["id"])
            )
        body.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
            % (
                row["created_at"], row["school_code"], labels.get(row["kind"], row["kind"]),
                row["code"], row["filename"], open_link, delete_cell,
            )
        )
    if can_delete:
        note = "Delete sirf Saini kar sakta hai. Isse cross-check copy hat-ti hai. Asli print file nahi mit-ti."
    else:
        note = "Sirf dekhne ke liye. School document bana sakta hai, delete nahi kar sakta."
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>%s</title>'
        '<style>body{font-family:Arial;max-width:980px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}'
        'main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}'
        'table{width:100%%;border-collapse:collapse;margin-top:12px}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px;vertical-align:top}'
        'button{background:#8d1d1d;color:white;border:0;border-radius:8px;padding:8px 12px}</style>'
        '</head><body><main><p><a href="/">Home</a></p><h1>%s</h1><p>%s</p>'
        '<table><tr><th>Date</th><th>School</th><th>Type</th><th>Code</th><th>File</th><th>Open</th><th></th></tr>%s</table>'
        '</main></body></html>'
    ) % (title, title, note, "".join(body))


def _send_archived(path):
    from flask import send_file
    inline = path.suffix.lower() == ".html"
    try:
        return send_file(str(path), as_attachment=not inline, download_name=path.name)
    except TypeError:
        return send_file(str(path), as_attachment=not inline, attachment_filename=path.name)


@app.route("/portal/archive")
def school_document_archive():
    import document_archive
    school = session.get("portal_school")
    if not school:
        return redirect("/school-login?next=/portal/archive")
    document_archive.scan(TRIAL_DIR)
    return _archive_page("Saved documents", document_archive.visible(TRIAL_DIR, school), False)


@app.route("/portal/archive-file")
def school_document_file():
    import document_archive
    school = session.get("portal_school")
    if not school:
        return redirect("/school-login")
    path = document_archive.file_for(TRIAL_DIR, request.args.get("id", "0"), school)
    if path is None:
        return ("Document not found", 404)
    return _send_archived(path)


@app.route("/saini/archive", methods=["GET", "POST"])
def saini_document_archive():
    import document_archive
    if not session.get("saini_teacher_authenticated"):
        return redirect(url_for("trial_login", next="/saini/archive"))
    if request.method == "POST":
        document_archive.remove(TRIAL_DIR, request.form.get("doc_id", "0"))
    document_archive.scan(TRIAL_DIR)
    return _archive_page("Document archive", document_archive.visible(TRIAL_DIR), True)


@app.route("/saini/archive-file")
def saini_document_file():
    import document_archive
    if not session.get("saini_teacher_authenticated"):
        return redirect(url_for("trial_login", next="/saini/archive"))
    path = document_archive.file_for(TRIAL_DIR, request.args.get("id", "0"))
    if path is None:
        return ("Document not found", 404)
    return _send_archived(path)
'''


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_guard(text):
    lines = text.splitlines()
    hits = [
        index for index, line in enumerate(lines)
        if "/portal/data" in line and "request.path" in line and "/portal/archive" not in line
    ]
    if len(hits) != 1:
        raise SystemExit("ABORT GUARD %s" % len(hits))
    line = lines[hits[0]]
    if '"/portal/data"' in line:
        line = line.replace('"/portal/data"', '"/portal/data", "/portal/archive", "/portal/archive-file"', 1)
    elif "'/portal/data'" in line:
        line = line.replace("'/portal/data'", "'/portal/data', '/portal/archive', '/portal/archive-file'", 1)
    else:
        raise SystemExit("ABORT GUARD_QUOTE")
    lines[hits[0]] = line
    print("GUARD yes")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def patch_paper_hook(text):
    key = '_paper_code = fname[7:-5] if fname.startswith("ACTUAL_") and fname.endswith(".docx") else fname'
    if text.count(key) != 1:
        raise SystemExit("ABORT PAPER_HOOK %s" % text.count(key))
    start = text.find(key)
    line_end = text.find("\n", start)
    indent = text[text.rfind("\n", 0, start) + 1:start]
    extra = (
        "\n" + indent + "try:\n"
        + indent + "    import document_archive as _document_archive\n"
        + indent + "    _document_archive.keep(TRIAL_DIR, _school_name, 'paper', _paper_code, fpath)\n"
        + indent + "except Exception:\n"
        + indent + "    pass"
    )
    print("PAPER_HOOK yes")
    return text[:line_end] + extra + text[line_end:]


def patch_links(text):
    swaps = (
        (
            "Only Saini can change a rate.",
            "Only Saini can change a rate. <a href=/saini/archive>Saved documents</a>",
        ),
        (
            '<a href="/saini/paper-rates">Paper rates (SAINI)</a>',
            '<a href="/saini/paper-rates">Paper rates (SAINI)</a> | <a href=/saini/archive>Saved documents</a>',
        ),
    )
    linked = 0
    for old, new in swaps:
        count = text.count(old)
        if count >= 1 and new not in text:
            text = text.replace(old, new)
            linked += count
    print("SAINI_LINKS %s" % linked)
    return text


def patch_data_link(text):
    old = '<a href="/portal/data">School data</a>'
    new = '<a href="/portal/data">School data</a> | <a href=/portal/archive>Saved documents</a>'
    if "/portal/archive" in text:
        print("DATA_LINK already")
        return text
    count = text.count(old)
    if count == 0:
        print("DATA_LINK 0")
        return text
    print("DATA_LINK %s" % count)
    return text.replace(old, new)


def _backup(path, label):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / label
    stamp = 2
    while target.exists():
        target = BACKUP_DIR / label.replace(".py", "_%s.py" % stamp)
        stamp += 1
    target.write_bytes(path.read_bytes())
    return target


def main():
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        raise SystemExit("ABORT ORIGINAL")
    if "/portal/archive" in APP.read_text(encoding="utf-8"):
        raise SystemExit("ABORT ALREADY")
    raw = APP.read_bytes()
    text = raw.decode("utf-8").replace("\r\n", "\n")
    marker = '\nif __name__ == "__main__":'
    if text.count(marker) != 1:
        raise SystemExit("ABORT MAIN %s" % text.count(marker))
    text = patch_guard(text)
    text = patch_paper_hook(text)
    text = patch_links(text)
    text = text.replace(marker, "\n" + ROUTES.strip() + "\n" + marker, 1)
    if text.count("def school_document_archive") != 1 or text.count("def saini_document_archive") != 1:
        raise SystemExit("ABORT ROUTES")
    data_raw = DATA.read_bytes() if DATA.is_file() else None
    data_text = None
    if data_raw is not None:
        data_text = patch_data_link(data_raw.decode("utf-8").replace("\r\n", "\n"))
    module = DEV / "document_archive.py"
    app_bak = _backup(APP, "subject_wizard_dev_before_archive.py")
    if data_raw is not None:
        _backup(DATA, "school_data_before_archive.py")
    module.write_text(MODULE, encoding="utf-8")
    if b"\r\n" in raw:
        text = text.replace("\n", "\r\n")
    if data_text is not None and b"\r\n" in data_raw:
        data_text = data_text.replace("\n", "\r\n")
    tmp = APP.with_name(APP.name + ".archive_tmp")
    data_tmp = DATA.with_name(DATA.name + ".archive_tmp")
    chk = APP.with_name(APP.name + ".archive_check.pyc")
    data_chk = DATA.with_name(DATA.name + ".archive_data_check.pyc")
    mod_chk = DEV / "document_archive.archive_check.pyc"
    try:
        tmp.write_bytes(text.encode("utf-8"))
        py_compile.compile(str(tmp), cfile=str(chk), doraise=True)
        py_compile.compile(str(module), cfile=str(mod_chk), doraise=True)
        if data_text is not None:
            data_tmp.write_bytes(data_text.encode("utf-8"))
            py_compile.compile(str(data_tmp), cfile=str(data_chk), doraise=True)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        data_tmp.unlink(missing_ok=True)
        raise SystemExit("ABORT COMPILE %s" % exc)
    finally:
        chk.unlink(missing_ok=True)
        data_chk.unlink(missing_ok=True)
        mod_chk.unlink(missing_ok=True)
    tmp.replace(APP)
    if data_text is not None:
        data_tmp.replace(DATA)
    import sys
    sys.path.insert(0, str(DEV))
    import document_archive
    try:
        count = document_archive.scan(DEV)
        rows = document_archive.visible(DEV)
    except BaseException as exc:
        APP.write_bytes(raw)
        if data_raw is not None:
            DATA.write_bytes(data_raw)
        raise SystemExit("ABORT SCAN %s" % exc)
    if sha256(ORIG) != ORIG_APP_HASH or sha256(ORIG_DB) != ORIG_DB_HASH:
        APP.write_bytes(raw)
        if data_raw is not None:
            DATA.write_bytes(data_raw)
        raise SystemExit("ABORT ORIGINAL_CHANGED")
    print("VISIBLE %s" % count)
    for row in rows[:15]:
        print("DOC %s %s %s" % (row["school_code"], row["kind"], row["code"]))
    print("PATCH_OK")
    print("folder=document_archive")
    print("school_view=/portal/archive")
    print("saini_delete=/saini/archive")
    print("backup=%s" % app_bak.name)
    print("original_app=%s" % sha256(ORIG))
    print("original_db=%s" % sha256(ORIG_DB))
    print("printer=not_started")


if __name__ == "__main__":
    main()
