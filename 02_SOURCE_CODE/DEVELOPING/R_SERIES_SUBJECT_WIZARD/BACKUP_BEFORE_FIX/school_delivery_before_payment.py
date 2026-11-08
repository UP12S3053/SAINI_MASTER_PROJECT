import base64
import hmac
import secrets
from datetime import datetime
from pathlib import Path

import school_registry

CARD_RATE = 20
SHEET_SIZE = 10

NEXT_STATUS = {
    "REQUESTED": "ACCEPTED",
    "ACCEPTED": "PRINTING",
    "PRINTING": "QC_PASSED",
    "QC_FAILED": "PRINTING",
    "QC_PASSED": "PACKED",
    "PACKED": "DISPATCHED",
}
NEXT_LABEL = {
    "REQUESTED": "Accept job",
    "ACCEPTED": "Start printing",
    "PRINTING": "QC passed",
    "QC_FAILED": "Reprint",
    "QC_PASSED": "Pack",
    "PACKED": "Dispatch",
}
SCHOOL_LABEL = {
    "REQUESTED": "Received",
    "ACCEPTED": "Accepted",
    "PRINTING": "Printing",
    "QC_FAILED": "Reprint",
    "QC_PASSED": "Checked",
    "PACKED": "Packed",
    "DISPATCHED": "Dispatched",
}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _esc(value):
    text = str(value)
    return (
        text.replace("&", "&" + "amp;")
        .replace("<", "&" + "lt;")
        .replace(">", "&" + "gt;")
        .replace('"', "&" + "quot;")
    )


def _yes(flag):
    return "YES" if flag else "NO"


def ensure_orders(conn):
    school_registry.assert_development_db(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_delivery_orders (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL,
        want_cards INTEGER NOT NULL, want_marksheets INTEGER NOT NULL,
        want_papers INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(school_delivery_orders)")}
    if "job_code" not in columns:
        conn.execute("ALTER TABLE school_delivery_orders ADD COLUMN job_code TEXT NOT NULL DEFAULT ''")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_delivery_events (
        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL,
        from_status TEXT NOT NULL, to_status TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_ledger (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, job_code TEXT NOT NULL,
        detail TEXT NOT NULL, qty INTEGER NOT NULL, rate INTEGER NOT NULL,
        amount INTEGER NOT NULL, created_at TEXT NOT NULL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_delivery_slots (
        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, position INTEGER NOT NULL,
        student_uid TEXT NOT NULL, student_name TEXT NOT NULL, class_name TEXT NOT NULL)"""
    )
    blank = conn.execute(
        "SELECT id, school_code FROM school_delivery_orders WHERE job_code=''"
    ).fetchall()
    for order_id, school_code in blank:
        conn.execute(
            "UPDATE school_delivery_orders SET job_code=? WHERE id=?",
            ("%s-%04d" % (school_code, order_id), order_id),
        )
    conn.commit()


def _guard_school(conn, school_code):
    row = conn.execute(
        "SELECT status, activated FROM school_accounts WHERE school_code=?",
        (school_code,),
    ).fetchone()
    if row is None or row[1] != 0 or row[0] != "DRAFT":
        raise ValueError("Only a DRAFT school can send a request")


def save_card_job(conn, school_code, copies, sheets, papers):
    ensure_orders(conn)
    _guard_school(conn, school_code)
    chosen = []
    for uid, raw in copies:
        try:
            count = int(raw or 0)
        except ValueError:
            raise ValueError("Copy count must be 0, 1, 2, or 3")
        if count < 0 or count > SHEET_SIZE:
            raise ValueError("Each student can have at most 10 copies on one job")
        if count:
            chosen.append((uid, count))
    total = sum(count for _, count in chosen)
    if total == 0 and not (sheets or papers):
        raise ValueError("Choose card copies, marksheets, or exam papers")
    if total and (total < SHEET_SIZE or total % SHEET_SIZE):
        raise ValueError(
            "ID cards print 10 on one A4 sheet. Total is %d. Use double or triple copies until it is 10, 20, or 30."
            % total
        )
    slots = []
    for uid, count in chosen:
        student = conn.execute(
            "SELECT student_name, class_name FROM school_students WHERE school_code=? AND student_uid=?",
            (school_code, uid),
        ).fetchone()
        if student is None:
            raise ValueError("Student is not in this school")
        slots.extend((uid, student[0], student[1]) for _ in range(count))
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    cursor = conn.execute(
        """INSERT INTO school_delivery_orders
        (school_code, want_cards, want_marksheets, want_papers, status, created_at, job_code)
        VALUES (?,?,?,?,'REQUESTED',?,'')""",
        (school_code, 1 if total else 0, 1 if sheets else 0, 1 if papers else 0, _now()),
    )
    order_id = cursor.lastrowid
    job_code = "%s-%04d" % (school_code, order_id)
    conn.execute("UPDATE school_delivery_orders SET job_code=? WHERE id=?", (job_code, order_id))
    conn.execute(
        """INSERT INTO school_delivery_events (order_id, from_status, to_status, created_at)
        VALUES (?,?,?,?)""",
        (order_id, "", "REQUESTED", _now()),
    )
    for position, slot in enumerate(slots, 1):
        conn.execute(
            """INSERT INTO school_delivery_slots
            (order_id, position, student_uid, student_name, class_name) VALUES (?,?,?,?,?)""",
            (order_id, position, slot[0], slot[1], slot[2]),
        )
    amount = 0
    if total:
        amount = total * CARD_RATE
        names = ", ".join("%s x%d" % pair for pair in chosen)
        detail = "ID cards, %d A4 sheet, %d cards. %s" % (total // SHEET_SIZE, total, names)
        conn.execute(
            """INSERT INTO school_ledger
            (school_code, job_code, detail, qty, rate, amount, created_at) VALUES (?,?,?,?,?,?,?)""",
            (school_code, job_code, detail[:500], total, CARD_RATE, amount, _now()),
        )
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if before != after:
        conn.rollback()
        raise ValueError("Refused")
    conn.commit()
    return job_code, amount


def card_job_form(conn, school_code, token):
    rows = conn.execute(
        """SELECT student_uid, class_name, student_name FROM school_students
        WHERE school_code=? ORDER BY class_name, student_name""",
        (school_code,),
    ).fetchall()
    lines = ""
    for uid, class_name, student_name in rows:
        lines += (
            "<tr><td>%s</td><td>%s</td><td>%s</td><td><select style=\"width:90px\" name=\"copy_%s\" onchange=\"tally()\">"
            "<option>0</option><option>1</option><option>2</option><option>3</option>"
            "<option>4</option><option>5</option><option>6</option><option>7</option>"
            "<option>8</option><option>9</option><option>10</option></select></td></tr>"
            % (_esc(uid), _esc(class_name), _esc(student_name), _esc(uid))
        )
    return (
        "<h2>ID card A4 job</h2><p>Production prints 10 cards on one A4 sheet, 2 by 5. "
        "A job needs 10, 20, or 30 cards. Copy one student 2 or 3 times to fill the sheet. "
        "Rate is Rs %d per card. The school account updates when the job is created.</p>"
        % CARD_RATE
        + '<form method="post">'
        + '<input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
        + '<input type="hidden" name="action" value="cardsheet">'
        + "<table><tr><th>UID</th><th>Class</th><th>Student</th><th>Copies</th></tr>"
        + lines + "</table><p id=\"tally\">0 cards</p>"
        + '<label><input type="checkbox" name="want_marksheets" value="1"> Result marksheets</label>'
        + '<label><input type="checkbox" name="want_papers" value="1"> Exam paper photostat</label>'
        + '<button type="submit">Create A4 job</button></form>'
        + "<script>function tally(){var n=0,nodes=document.querySelectorAll('select[name^=copy_]');"
        + "for(var i=0;i<nodes.length;i++)n+=+nodes[i].value;var ok=n>=10&&n%10==0;"
        + "document.getElementById('tally').textContent=n+' cards'"
        + "+(ok?', '+n/10+' A4 sheet, Rs '+(n*" + str(CARD_RATE) + "):'. Need 10, 20, or 30.');}</script>"
    )


def account_block(conn, school_code):
    ensure_orders(conn)
    rows = conn.execute(
        """SELECT created_at, job_code, detail, qty, rate, amount
        FROM school_ledger WHERE school_code=? ORDER BY id""",
        (school_code,),
    ).fetchall()
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(row[0]), _esc(row[1]), _esc(row[2]), row[3], row[4], row[5])
        for row in rows
    )
    total = sum(row[5] for row in rows)
    return (
        "<h1>School account</h1><p>Showing only " + _esc(school_code)
        + ". This khata updates by itself when an ID card job is created. Rate Rs %d per card.</p>"
        % CARD_RATE
        + "<table><tr><th>Date</th><th>Job</th><th>Detail</th><th>Cards</th><th>Rate</th><th>Amount</th></tr>"
        + body + "</table><h2>Balance due</h2><p>Rs %d</p>" % total
        + '<p><a href="/portal/data">School data</a></p>'
    )


def _slot_sheet(conn, order_id, school_code):
    rows = conn.execute(
        """SELECT position, student_uid, class_name, student_name
        FROM school_delivery_slots WHERE order_id=? ORDER BY position""",
        (order_id,),
    ).fetchall()
    if not rows:
        return ""
    body = ""
    sheet = 0
    for position, uid, class_name, student_name in rows:
        if (position - 1) % SHEET_SIZE == 0:
            sheet += 1
            body += '<tr><td colspan="5"><strong>A4 sheet %d, 2 x 5</strong></td></tr>' % sheet
        body += "<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            ((position - 1) % SHEET_SIZE) + 1, _esc(uid), _esc(class_name), _esc(student_name),
            _face(conn, school_code, uid, uid),
        )
    return (
        "<h2>ID cards</h2><table><tr><th>Place</th><th>UID</th><th>Class</th><th>Student</th><th>Photo</th></tr>"
        + body + "</table>"
    )


def save_order(conn, school_code, cards, sheets, papers):
    ensure_orders(conn)
    if cards:
        raise ValueError("ID cards print 10 on one A4 sheet. Use the card job form, not this tick box.")
    flags = (0, 1 if sheets else 0, 1 if papers else 0)
    if sum(flags) == 0:
        raise ValueError("Choose ID cards, marksheets, or exam papers")
    _guard_school(conn, school_code)
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    cursor = conn.execute(
        """INSERT INTO school_delivery_orders
        (school_code, want_cards, want_marksheets, want_papers, status, created_at, job_code)
        VALUES (?,?,?,?,'REQUESTED',?,'')""",
        (school_code, flags[0], flags[1], flags[2], _now()),
    )
    job_code = "%s-%04d" % (school_code, cursor.lastrowid)
    conn.execute(
        "UPDATE school_delivery_orders SET job_code=? WHERE id=?",
        (job_code, cursor.lastrowid),
    )
    conn.execute(
        """INSERT INTO school_delivery_events (order_id, from_status, to_status, created_at)
        VALUES (?,?,?,?)""",
        (cursor.lastrowid, "", "REQUESTED", _now()),
    )
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if before != after:
        conn.rollback()
        raise ValueError("Refused")
    conn.commit()
    return job_code


def advance_order(conn, order_id, action):
    ensure_orders(conn)
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    row = conn.execute(
        "SELECT status, school_code FROM school_delivery_orders WHERE id=?",
        (order_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Order not found")
    current = row[0]
    if action == "fail":
        if current != "PRINTING":
            raise ValueError("Quality check applies only while printing")
        target = "QC_FAILED"
    elif action == "next":
        target = NEXT_STATUS.get(current)
        if not target:
            raise ValueError("This job is already dispatched")
    else:
        raise ValueError("Unknown action")
    changed = conn.execute(
        "UPDATE school_delivery_orders SET status=? WHERE id=? AND status=?",
        (target, order_id, current),
    ).rowcount
    if changed != 1:
        conn.rollback()
        raise ValueError("Job changed. Reload the queue.")
    conn.execute(
        """INSERT INTO school_delivery_events (order_id, from_status, to_status, created_at)
        VALUES (?,?,?,?)""",
        (order_id, current, target, _now()),
    )
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if before != after:
        conn.rollback()
        raise ValueError("Refused")
    conn.commit()
    return target


def orders_table(conn, school_code):
    ensure_orders(conn)
    rows = conn.execute(
        """SELECT job_code, want_cards, want_marksheets, want_papers, status, created_at
        FROM school_delivery_orders WHERE school_code=? ORDER BY id DESC""",
        (school_code,),
    ).fetchall()
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(row[0]), _yes(row[1]), _yes(row[2]), _yes(row[3]), _esc(SCHOOL_LABEL.get(row[4], row[4])), _esc(row[5]))
        for row in rows
    )
    return (
        "<h2>Delivery jobs</h2><table><tr><th>Job</th><th>ID cards</th><th>Marksheets</th>"
        "<th>Papers</th><th>Stage</th><th>Time</th></tr>" + body + "</table>"
        + "<p>Saini prints, checks, packs, and dispatches. The school cannot print.</p>"
    )


def _sheet(title, headers, rows):
    head = "".join("<th>%s</th>" % _esc(name) for name in headers)
    body = "".join(
        "<tr>" + "".join("<td>%s</td>" % _esc(cell) for cell in row) + "</tr>"
        for row in rows
    )
    return "<h2>%s</h2><table><tr>%s</tr>%s</table>" % (_esc(title), head, body)


def _face(conn, school_code, uid, stored):
    if not stored:
        return "NO"
    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent
    if root.name != "DEVELOPMENT_SUBJECT_WIZARD":
        return "NO"
    folder = (root / "school_photos" / school_code).resolve()
    path = (folder / (str(uid) + ".jpg")).resolve()
    if path.parent != folder or not path.is_file():
        return "NO"
    raw = path.read_bytes()
    kind = "png" if raw.startswith(b"\x89PNG") else "jpeg"
    return (
        '<img class="face" alt="" src="data:image/'
        + kind
        + ";base64,"
        + base64.b64encode(raw).decode("ascii")
        + '">'
    )


def _card_sheet(conn, school_code):
    rows = conn.execute(
        """SELECT student_uid, class_name, student_name, father_name, mobile, address, photo_path
        FROM school_students WHERE school_code=? ORDER BY class_name, student_name""",
        (school_code,),
    ).fetchall()
    body = ""
    for item in rows:
        cells = "".join("<td>%s</td>" % _esc(cell) for cell in item[:6])
        cells += "<td>%s</td>" % _face(conn, school_code, item[0], item[6])
        body += "<tr>" + cells + "</tr>"
    return _sheet("ID cards", ("UID", "Class", "Student", "Father", "Mobile", "Address", "Photo"), [])[:-8] + body + "</table>"


def _job_card(conn, order_id):
    row = conn.execute(
        """SELECT job_code, school_code, want_cards, want_marksheets, want_papers, status, created_at
        FROM school_delivery_orders WHERE id=?""",
        (order_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Job not found")
    school = conn.execute(
        "SELECT school_name, city, status, activated FROM school_accounts WHERE school_code=?",
        (row[1],),
    ).fetchone()
    name = school[0] if school else row[1]
    city = school[1] if school else ""
    sections = ""
    if row[2]:
        order_pk = conn.execute(
            "SELECT id FROM school_delivery_orders WHERE job_code=?", (row[0],)
        ).fetchone()[0]
        sections += _slot_sheet(conn, order_pk, row[1]) or _card_sheet(conn, row[1])
    if row[3]:
        marks = conn.execute(
            """SELECT student_uid, subject, exam_slot, obtained, max_marks
            FROM school_marks WHERE school_code=? ORDER BY student_uid, subject, exam_slot""",
            (row[1],),
        ).fetchall()
        sections += _sheet("Result marksheets", ("UID", "Subject", "Exam", "Obtained", "Max"), marks)
    if row[4]:
        papers = conn.execute(
            """SELECT class_name, subject, student_strength, max_marks
            FROM school_paper_needs WHERE school_code=? ORDER BY class_name, subject""",
            (row[1],),
        ).fetchall()
        sections += _sheet("Exam paper photostat", ("Class", "Subject", "Strength", "Max"), papers)
    if not sections:
        sections = "<p>This job has no work lines.</p>"
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><title>Job ' + _esc(row[0]) + "</title><style>"
        "body{font-family:Arial,sans-serif;max-width:980px;margin:24px auto;padding:16px;color:#172033}"
        "table{width:100%;border-collapse:collapse}td,th{border:1px solid #d8dee9;text-align:left;padding:6px}"
        "button{background:#17365d;color:#fff;border:0;border-radius:8px;padding:8px 12px}"
        "@media print{.noprint{display:none}}img.face{width:78px;height:98px;object-fit:cover;display:block}"
        '</style></head><body><p class="noprint"><a href="/saini-queue">Queue</a></p>'
        + "<h1>Job " + _esc(row[0]) + "</h1><p>" + _esc(name) + ", " + _esc(city)
        + ". Stage " + _esc(SCHOOL_LABEL.get(row[5], row[5])) + ". School status stays DRAFT.</p>"
        + "<p>Cards " + _yes(row[2]) + ". Marksheets " + _yes(row[3]) + ". Papers " + _yes(row[4])
        + ". Opened " + _esc(row[6]) + ".</p>"
        + '<p class="noprint"><button type="button" onclick="window.print()">Print shop sheet</button></p>'
        + sections + "</body></html>"
    )
    return page


def _button(token, order_id, action, label):
    return (
        '<form method="post" style="display:inline">'
        + '<input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
        + '<input type="hidden" name="order_id" value="' + str(order_id) + '">'
        + '<input type="hidden" name="action" value="' + action + '">'
        + '<button type="submit">' + _esc(label) + "</button></form>"
    )


def saini_queue(get_db, request, session):
    conn = get_db()
    ensure_orders(conn)
    error = ""
    notice = ""
    token = session.get("saini_queue_csrf") or secrets.token_hex(16)
    session["saini_queue_csrf"] = token
    if request.method == "POST":
        posted = request.form.get("csrf_token", "")
        if not posted or not hmac.compare_digest(posted, token):
            error = "Security token expired. Reload the page."
        else:
            try:
                target = advance_order(
                    conn, int(request.form.get("order_id", "0")), request.form.get("action", "")
                )
                notice = "Job moved to " + SCHOOL_LABEL.get(target, target)
            except ValueError as exc:
                error = str(exc)
        session["saini_queue_csrf"] = secrets.token_hex(16)
        token = session["saini_queue_csrf"]
    job_text = (request.args.get("job") or "").strip()
    if request.method == "GET" and job_text.isdigit():
        try:
            return _job_card(conn, int(job_text))
        except ValueError as exc:
            error = str(exc)
    stage = (request.args.get("stage") or "").strip().upper()
    if stage not in NEXT_STATUS and stage != "DISPATCHED":
        stage = ""
    sql = """SELECT id, job_code, school_code, want_cards, want_marksheets, want_papers, status, created_at
        FROM school_delivery_orders"""
    args = ()
    if stage:
        sql += " WHERE status=?"
        args = (stage,)
    sql += " ORDER BY id DESC"
    rows = conn.execute(sql, args).fetchall()
    body = ""
    for row in rows:
        action = ""
        if row[6] in NEXT_LABEL:
            action = _button(token, row[0], "next", NEXT_LABEL[row[6]])
        if row[6] == "PRINTING":
            action += " " + _button(token, row[0], "fail", "QC failed")
        if not action:
            action = "Done"
        body += "<tr><td><a href=\"/saini-queue?job=%s\">%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            row[0], _esc(row[1]), _esc(row[2]), _yes(row[3]), _yes(row[4]), _yes(row[5]),
            _esc(SCHOOL_LABEL.get(row[6], row[6])), _esc(row[7]), action,
        )
    filters = '<p><a href="/saini-queue">All</a>'
    for name in ("REQUESTED", "ACCEPTED", "PRINTING", "QC_PASSED", "PACKED", "DISPATCHED"):
        filters += ' | <a href="/saini-queue?stage=%s">%s</a>' % (name, SCHOOL_LABEL[name])
    filters += "</p>"
    flag = ('<p class="bad">%s</p>' % _esc(error)) if error else ""
    flag += ('<p class="ok">%s</p>' % _esc(notice)) if notice else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Saini delivery queue</title><style>'
        "body{font-family:Arial,sans-serif;max-width:980px;margin:24px auto;padding:16px;background:#f5f7fa;color:#172033}"
        "main{background:#fff;border:1px solid #d8dee9;border-radius:12px;padding:22px}"
        "table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:7px;vertical-align:top}"
        "button{background:#17365d;color:#fff;border:0;border-radius:8px;padding:8px 12px;width:auto}"
        ".ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"
        "</style></head><body><main><p><a href=\"/\">Home</a></p><h1>Central production queue</h1>"
        "<p>Saini accepts, prints, checks, packs, and dispatches. Schools only request. Nothing is activated.</p>"
        + filters + flag
        + "<table><tr><th>Job</th><th>School</th><th>Cards</th><th>Marksheets</th><th>Papers</th><th>Stage</th><th>Time</th><th>Next</th></tr>"
        + body + "</table></main></body></html>"
    )
