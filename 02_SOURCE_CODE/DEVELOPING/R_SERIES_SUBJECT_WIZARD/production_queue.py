"""One production line for the desktop programs. Schools join. They never receive the files."""

from datetime import datetime
from pathlib import Path

import school_registry

PROGRAMS = (
    ("ID_CARD", "ID cards", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\MAIN_ASSISTANT.py",
     'py "{path}" --school {school} --mode B --no-launch'),
    ("PHOTO", "Photo lab", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_AI_STUDIO\run_studio_pipeline.py",
     'py "{path}"'),
    ("PAPER", "Exam paper printing", r"D:\SHRI_JAI_SHRI_RAM\project_panels\EXAM_PAPER_PROJECT\PRINT_MANAGER.py",
     'py "{path}" --plan-only'),
    ("ADMIT", "Admit cards", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\SAINI_ID_CARD.py",
     'py "{path}"'),
    ("MARKSHEET", "Marksheet files", r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\SAINI_ID_CARD.py",
     'py "{path}"'),
)
BY_CODE = {item[0]: item for item in PROGRAMS}
ACTIVE = ("WAITING", "HELD")


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
    return "Joined the %s line. Your place is %d. The files stay on Saini's computer." % (BY_CODE[kind][1], place)


def _ticket(conn, row_id, school_code, kind):
    code, label, path, command = BY_CODE[kind]
    folder = _root(conn) / "production_tickets"
    folder.mkdir(exist_ok=True)
    target = folder / ("JOB-%04d.txt" % row_id)
    text = "\n".join([
        "SAINI PRODUCTION TICKET",
        "School: " + school_code,
        "Work: " + label,
        "Program stays on this computer:",
        path,
        "Do not send this program or this ticket to the school.",
        "Run only this school. The photo folder, Excel, and printer are shared.",
        "Command:",
        command.format(path=path, school=school_code),
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
    return "Taken %s for %s. Ticket: %s" % (BY_CODE[row[2]][1], row[1], ticket)


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
    rows = conn.execute(
        """SELECT id, kind, status, created_at FROM production_line
        WHERE school_code=? ORDER BY id DESC LIMIT 12""",
        (school_code,),
    ).fetchall()
    ahead = conn.execute(
        "SELECT COUNT(*) FROM production_line WHERE status IN ('WAITING','HELD')"
    ).fetchone()[0]
    mine = conn.execute(
        """SELECT COUNT(*) FROM production_line
        WHERE school_code=? AND status IN ('WAITING','HELD')""",
        (school_code,),
    ).fetchone()[0]
    buttons = ""
    hidden = '<input type="hidden" name="csrf_token" value="%s">' % _esc(token)
    for code, label, _path, _command in PROGRAMS:
        buttons += (
            '<form method="post">%s<input type="hidden" name="action" value="join">'
            '<input type="hidden" name="kind" value="%s">'
            '<button type="submit">Join line: %s</button></form>'
        ) % (hidden, code, _esc(label))
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(BY_CODE[row[1]][1]), _esc(row[2]), _place(conn, row[0]) if row[2] in ACTIVE else "-", _esc(row[3]))
        for row in rows
    )
    return (
        "<p>These tools stay on Saini's computer. A school only joins the line. "
        "One school runs at a time because the photo folder, Excel, and printer are shared. "
        "Schools ahead of you: %d. Your open requests: %d.</p>"
        % (max(0, ahead - mine), mine)
        + buttons
        + "<table><tr><th>Work</th><th>Status</th><th>Place</th><th>Time</th></tr>"
        + body + "</table>"
    )


def saini_block(conn, token):
    ensure_schema(conn)
    rows = conn.execute(
        """SELECT id, school_code, kind, status, ticket_path FROM production_line
        WHERE status IN ('WAITING','HELD') ORDER BY id"""
    ).fetchall()
    body = "".join(
        "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (row[0], _esc(row[1]), _esc(BY_CODE.get(row[2], (row[2], row[2]))[1]), _esc(row[3]), _esc(row[4]))
        for row in rows
    ) or '<tr><td colspan="5">No school is waiting.</td></tr>'
    hidden = '<input type="hidden" name="csrf_token" value="%s">' % _esc(token)
    return (
        "<h2>Desktop production line</h2>"
        "<p>MAIN_ASSISTANT, photo lab, PRINT_MANAGER, and SAINI_ID_CARD stay on this computer. "
        "Take one school, finish it, then take the next. Do not run two together.</p>"
        + '<form method="post">%s<input type="hidden" name="action" value="take_line">'
        % hidden
        + '<button type="submit">Take next school</button></form>'
        + '<form method="post">%s<input type="hidden" name="action" value="finish_line">'
        % hidden
        + '<input type="hidden" name="ok" value="1"><button type="submit">Mark done and release</button></form>'
        + '<form method="post">%s<input type="hidden" name="action" value="finish_line">'
        % hidden
        + '<input type="hidden" name="ok" value="0"><button type="submit">Mark failed and release</button></form>'
        + "<table><tr><th>ID</th><th>School</th><th>Work</th><th>Status</th><th>Ticket</th></tr>"
        + body + "</table>"
    )
