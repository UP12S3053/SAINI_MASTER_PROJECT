# -*- coding: utf-8 -*-
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
