"""One production line for the desktop programs. Schools join. They never receive the files."""

from datetime import datetime, timedelta
from pathlib import Path

import school_registry

PROGRAMS = (
    ("ID_CARD", "ID cards", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\MAIN_ASSISTANT.py",
     'py "{path}" --school {school} --mode B --no-launch'),
    ("PHOTO", "Photo lab", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_AI_STUDIO\run_studio_pipeline.py",
     'py "{path}"'),
    ("PAPER", "Exam paper printing", r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\PRINT_MANAGER.py",
     'py "{path}" --excel "{excel}" --plan-only'),
    ("ADMIT", "Admit cards", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\SAINI_ID_CARD.py",
     'py "{path}"'),
    ("MARKSHEET", "Marksheet files", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\SAINI_ID_CARD.py",
     'py "{path}"'),
)
BY_CODE = {item[0]: item for item in PROGRAMS}
ACTIVE = ("WAITING", "HELD")
# One school on the machine. These are shop estimates, not a promise.
MINUTES = {
    "ID_CARD": 15,
    "PHOTO": 20,
    "PAPER": 20,
    "ADMIT": 15,
    "MARKSHEET": 15,
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _esc(value):
    text = str(value)
    amp = "&" + "amp;"
    return (
        text.replace("&", amp)
        .replace("<", "&" + "lt;")
        .replace(">", "&" + "gt;")
        .replace('"', "&" + "quot;")
    )


def ensure_schema(conn):
    school_registry.assert_development_db(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS production_line (
        id INTEGER PRIMARY KEY,
        school_code TEXT NOT NULL,
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        taken_at TEXT,
        finished_at TEXT,
        ticket_path TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '')"""
    )
    conn.commit()


def _root(conn):
    path = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    if path.parent.name != "DEVELOPMENT_SUBJECT_WIZARD":
        raise RuntimeError("REFUSED: production line can write only inside the development folder")
    return path.parent


def _place(conn, row_id):
    return conn.execute(
        "SELECT COUNT(*) FROM production_line WHERE status IN ('WAITING','HELD') AND id<=?",
        (row_id,),
    ).fetchone()[0]


def _stamp(text):
    try:
        return datetime.strptime(text or "", "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _left(kind, status, taken_at, now):
    full = MINUTES.get(kind, 15)
    if status == "WAITING":
        return full
    if status != "HELD":
        return 0
    started = _stamp(taken_at)
    used = int((now - started).total_seconds() // 60) if started else 0
    return max(5, full - used)


def _wait_minutes(conn, row_id, now):
    total = 0
    rows = conn.execute(
        """SELECT id, kind, status, taken_at FROM production_line
        WHERE status IN ('WAITING','HELD') AND id<? ORDER BY id""",
        (row_id,),
    )
    for row in rows:
        total += _left(row[1], row[2], row[3], now)
    return total


def _clock(minutes, now):
    start = now + timedelta(minutes=minutes)
    if start.date() == now.date():
        return start.strftime("%H:%M")
    return start.strftime("%d %b %H:%M")


def _start_text(conn, row_id, kind, status, taken_at, now):
    if status == "HELD":
        return "on the machine, about %d min left" % _left(kind, status, taken_at, now)
    if status != "WAITING":
        return "-"
    wait = _wait_minutes(conn, row_id, now)
    if wait <= 0:
        return "as soon as Saini takes it"
    return "around %s (%d min)" % (_clock(wait, now), wait)


def _timing_line(conn, school_code, now):
    first = conn.execute(
        """SELECT id, kind, status, taken_at FROM production_line
        WHERE school_code=? AND status IN ('WAITING','HELD') ORDER BY id LIMIT 1""",
        (school_code,),
    ).fetchone()
    if first is None:
        return "You have no open request. Join a line only when the school is ready."
    if first[2] == "HELD":
        return "Your job is on the machine now. About %d minutes left." % _left(first[1], first[2], first[3], now)
    ahead = conn.execute(
        "SELECT COUNT(*) FROM production_line WHERE status IN ('WAITING','HELD') AND id<?",
        (first[0],),
    ).fetchone()[0]
    wait = _wait_minutes(conn, first[0], now)
    if ahead <= 0 or wait <= 0:
        return "No job is ahead of you. Your work starts as soon as Saini takes the line."
    return "%d job(s) before you need about %d minutes. Your work starts around %s." % (ahead, wait, _clock(wait, now))


def join_line(conn, school_code, kind):
    ensure_schema(conn)
    school_code = (school_code or "").strip().upper()
    kind = (kind or "").strip().upper()
    if kind not in BY_CODE:
        raise ValueError("Choose one production line")
    existing = conn.execute(
        """SELECT id FROM production_line
        WHERE school_code=? AND kind=? AND status IN ('WAITING','HELD')""",
        (school_code, kind),
    ).fetchone()
    if existing:
        raise ValueError("This school is already in that line")
    conn.execute(
        """INSERT INTO production_line (school_code, kind, status, created_at)
        VALUES (?,?, 'WAITING', ?)""",
        (school_code, kind, _now()),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    place = _place(conn, row_id)
    when = _start_text(conn, row_id, kind, "WAITING", None, datetime.now())
    return "Joined the %s line. Your place is %d. Starts %s. The files stay on Saini's computer." % (
        BY_CODE[kind][1], place, when)



def _paper_sheet(conn, row_id, school_code):
    """One school's paper list for Print Manager. The master PAPER.xlsx is not touched."""
    root = _root(conn)
    folder = root / "production_jobs" / ("JOB-%04d" % row_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "PAPER_PRINT.xlsx"
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    rows = []
    if "school_paper_needs" in tables:
        rows = list(conn.execute(
            """SELECT class_name, subject, student_strength, max_marks
            FROM school_paper_needs WHERE school_code=? ORDER BY class_name, subject""",
            (school_code,),
        ))
    found = []
    out = root / "output_shortlisting_v2"
    if out.is_dir():
        found = [path for path in out.iterdir() if path.is_file() and school_code.upper() in path.name.upper()]
    from openpyxl import Workbook
    book = Workbook()
    sheet = book.active
    sheet.title = "PAPER"
    sheet.append(["SCHOOL NAME", "CLASS", "SUBJECT", "STUDENTS", "SHEETS_PER_COPY", "MM", "SOURCE_FILE", "LAYOUT", "PRINTED_SHEETS"])
    for class_name, subject, strength, marks in rows:
        source = ""
        klass = str(class_name).upper()
        short = str(subject).upper()[:3]
        for path in found:
            name = path.name.upper()
            if klass in name and short in name:
                source = str(path)
                break
        sheet.append([school_code, class_name, subject, int(strength or 0), 1, marks, source, "2-UP", 0])
    book.save(target)
    note = "paper_rows=%d excel=%s printer=not_started master_PAPER_xlsx=unchanged" % (len(rows), target)
    conn.execute("UPDATE production_line SET note=? WHERE id=?", (note, row_id))
    conn.commit()
    return str(target), note


def _ticket(conn, row_id, school_code, kind):
    code, label, path, command = BY_CODE[kind]
    folder = _root(conn) / "production_tickets"
    folder.mkdir(exist_ok=True)
    target = folder / ("JOB-%04d.txt" % row_id)
    extra = ""
    excel = ""
    if kind == "PAPER":
        excel, extra = _paper_sheet(conn, row_id, school_code)
        extra = extra + "\nPrint Manager gets only this school. Do not add --print."
    text = "\n".join([
        "SAINI PRODUCTION TICKET",
        "School: " + school_code,
        "Work: " + label,
        "Program stays on this computer:",
        path,
        "Do not send this program or this ticket to the school.",
        "Run only this school. The photo folder, Excel, and printer are shared.",
        "Command:",
        command.format(path=path, school=school_code, excel=excel),
        extra,
        "The desktop program may still ask a question. Answer it on this computer.",
        "",
    ])
    target.write_text(text, encoding="utf-8")
    return str(target)


def take_next(conn):
    ensure_schema(conn)
    held = conn.execute("SELECT id, school_code FROM production_line WHERE status='HELD'").fetchone()
    if held:
        raise ValueError("Finish %s first. Two schools cannot use the machine together." % held[1])
    row = conn.execute(
        """SELECT id, school_code, kind FROM production_line
        WHERE status='WAITING' ORDER BY id LIMIT 1"""
    ).fetchone()
    if row is None:
        raise ValueError("The production line is empty")
    ticket = _ticket(conn, row[0], row[1], row[2])
    conn.execute(
        "UPDATE production_line SET status='HELD', taken_at=?, ticket_path=? WHERE id=? AND status='WAITING'",
        (_now(), ticket, row[0]),
    )
    conn.commit()
    note = conn.execute("SELECT note FROM production_line WHERE id=?", (row[0],)).fetchone()
    detail = (" " + note[0]) if note and note[0] else ""
    return "Taken %s for %s.%s Ticket: %s" % (BY_CODE[row[2]][1], row[1], detail, ticket)


def finish_current(conn, ok):
    ensure_schema(conn)
    row = conn.execute("SELECT id FROM production_line WHERE status='HELD' ORDER BY id LIMIT 1").fetchone()
    if row is None:
        raise ValueError("No school is on the machine")
    status = "DONE" if ok else "FAILED"
    conn.execute(
        "UPDATE production_line SET status=?, finished_at=? WHERE id=? AND status='HELD'",
        (status, _now(), row[0]),
    )
    conn.commit()
    return "Line released. Status " + status


def school_block(conn, school_code, token):
    ensure_schema(conn)
    now = datetime.now()
    rows = conn.execute(
        """SELECT id, kind, status, created_at, taken_at FROM production_line
        WHERE school_code=? ORDER BY id DESC LIMIT 12""",
        (school_code,),
    ).fetchall()
    buttons = ""
    hidden = '<input type="hidden" name="csrf_token" value="%s">' % _esc(token)
    for code, label, _path, _command in PROGRAMS:
        buttons += (
            '<form method="post">%s<input type="hidden" name="action" value="join">'
            '<input type="hidden" name="kind" value="%s">'
            '<button type="submit">Join line: %s</button></form>'
        ) % (hidden, code, _esc(label))
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            _esc(BY_CODE[row[1]][1]),
            _esc(row[2]),
            _place(conn, row[0]) if row[2] in ACTIVE else "-",
            _esc(row[3]),
            _esc(_start_text(conn, row[0], row[1], row[2], row[4], now)),
        )
        for row in rows
    )
    rates = "ID cards %d, photo lab %d, exam paper %d, admit cards %d, marksheet %d." % (
        MINUTES["ID_CARD"], MINUTES["PHOTO"], MINUTES["PAPER"], MINUTES["ADMIT"], MINUTES["MARKSHEET"])
    return (
        "<p>" + _esc(_timing_line(conn, school_code, now)) + "</p>"
        "<p>These tools stay on Saini's computer. A school only joins the line. "
        "One school runs at a time. Estimate for one job, in minutes: " + rates +
        " A job already on the machine counts only the minutes still left. "
        "If a job runs long, the next start time moves later.</p>"
        + buttons
        + "<table><tr><th>Work</th><th>Status</th><th>Place</th><th>Joined</th><th>Starts about</th></tr>"
        + body + "</table>"
    )


def saini_block(conn, token):
    ensure_schema(conn)
    now = datetime.now()
    held = conn.execute(
        """SELECT id, school_code FROM production_line
        WHERE kind='PAPER' AND status IN ('WAITING','HELD') ORDER BY id"""
    ).fetchall()
    for row in held:
        _paper_sheet(conn, row[0], row[1])
    paper_note = conn.execute(
        """SELECT school_code, note FROM production_line
        WHERE kind='PAPER' AND status IN ('WAITING','HELD') AND note<>'' ORDER BY id"""
    ).fetchall()
    paper_line = "".join(
        "<p>Paper plan for %s: %s</p>" % (_esc(row[0]), _esc(row[1]))
        for row in paper_note
    )
    rows = conn.execute(
        """SELECT id, school_code, kind, status, ticket_path, taken_at FROM production_line
        WHERE status IN ('WAITING','HELD') ORDER BY id"""
    ).fetchall()
    body = "".join(
        "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            row[0], _esc(row[1]), _esc(BY_CODE.get(row[2], (row[2], row[2]))[1]),
            _esc(row[3]), _esc(_start_text(conn, row[0], row[2], row[3], row[5], now)), _esc(row[4]),
        )
        for row in rows
    ) or '<tr><td colspan="6">No school is waiting.</td></tr>'
    hidden = '<input type="hidden" name="csrf_token" value="%s">' % _esc(token)
    return (
        "<h2>Desktop production line</h2>"
        "<p>MAIN_ASSISTANT, photo lab, PRINT_MANAGER, and SAINI_ID_CARD stay on this computer. "
        "Take one school, finish it, then take the next. Do not run two together.</p>"
        + paper_line
        + '<form method="post">%s<input type="hidden" name="action" value="take_line">'
        % hidden
        + '<button type="submit">Take next school</button></form>'
        + '<form method="post">%s<input type="hidden" name="action" value="finish_line">'
        % hidden
        + '<input type="hidden" name="ok" value="1"><button type="submit">Mark done and release</button></form>'
        + '<form method="post">%s<input type="hidden" name="action" value="finish_line">'
        % hidden
        + '<input type="hidden" name="ok" value="0"><button type="submit">Mark failed and release</button></form>'
        + "<table><tr><th>ID</th><th>School</th><th>Work</th><th>Status</th><th>Starts about</th><th>Ticket</th></tr>"
        + body + "</table>"
    )
