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
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_payments (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, amount INTEGER NOT NULL,
        status TEXT NOT NULL, image_path TEXT NOT NULL, created_at TEXT NOT NULL,
        approved_at TEXT NOT NULL DEFAULT '')"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_dispatch (
        id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL UNIQUE,
        mode TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_shipping (
        school_code TEXT PRIMARY KEY, recipient TEXT NOT NULL, mobile TEXT NOT NULL,
        address TEXT NOT NULL, mode TEXT NOT NULL, confirmed_at TEXT NOT NULL)"""
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


def _money(conn, school_code):
    ensure_orders(conn)
    charges = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM school_ledger WHERE school_code=?",
        (school_code,),
    ).fetchone()[0]
    approved = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM school_payments WHERE school_code=? AND status='APPROVED'",
        (school_code,),
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM school_payments WHERE school_code=? AND status='PENDING'",
        (school_code,),
    ).fetchone()[0]
    return charges, approved, pending, charges - approved


def _proof_img(conn, stored):
    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent
    path = (root / stored).resolve()
    if root not in path.parents or not path.is_file():
        return ""
    raw = path.read_bytes()
    if len(raw) > 1500000:
        return "Too large to preview"
    kind = "png" if raw.startswith(b"\x89PNG") else "jpeg"
    return '<img style="width:140px;height:auto" alt="" src="data:image/' + kind + ';base64,' + base64.b64encode(raw).decode("ascii") + '">'


def save_payment(conn, school_code, amount, proof):
    ensure_orders(conn)
    _guard_school(conn, school_code)
    try:
        rupees = int(str(amount).strip())
    except (TypeError, ValueError):
        raise ValueError("Enter the amount in rupees")
    if rupees < 1:
        raise ValueError("Enter the amount in rupees")
    charges, approved, pending, due = _money(conn, school_code)
    if rupees > due - pending:
        raise ValueError("Amount is more than the balance still open")
    if proof is None or not getattr(proof, "filename", ""):
        raise ValueError("Upload the PhonePe screenshot")
    raw = proof.read()
    if not raw or len(raw) > 1500000:
        raise ValueError("Screenshot must be a JPG or PNG under 1.5 MB")
    if raw.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    elif raw.startswith(b"\x89PNG"):
        suffix = ".png"
    else:
        raise ValueError("Screenshot must be a JPG or PNG")
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    cursor = conn.execute(
        """INSERT INTO school_payments
        (school_code, amount, status, image_path, created_at, approved_at)
        VALUES (?,?,'PENDING','',?,'')""",
        (school_code, rupees, _now()),
    )
    payment_id = cursor.lastrowid
    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent
    folder = (root / "school_payments" / school_code).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    target = (folder / ("%d%s" % (payment_id, suffix))).resolve()
    if folder not in target.parents:
        conn.rollback()
        raise ValueError("Unsafe payment path")
    target.write_bytes(raw)
    relative = target.relative_to(root).as_posix()
    conn.execute("UPDATE school_payments SET image_path=? WHERE id=?", (relative, payment_id))
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if before != after:
        conn.rollback()
        raise ValueError("Refused")
    conn.commit()
    return "Rs %d pending for approval" % rupees


def approve_payment(conn, payment_id):
    ensure_orders(conn)
    row = conn.execute(
        "SELECT amount, status FROM school_payments WHERE id=?",
        (payment_id,),
    ).fetchone()
    if row is None or row[1] != "PENDING":
        raise ValueError("Payment is not waiting")
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    changed = conn.execute(
        "UPDATE school_payments SET status='APPROVED', approved_at=? WHERE id=? AND status='PENDING'",
        (_now(), payment_id),
    ).rowcount
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if changed != 1 or before != after:
        conn.rollback()
        raise ValueError("Refused")
    conn.commit()
    return row[0]


def account_block(conn, school_code, token):
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
    charges, approved, pending, due = _money(conn, school_code)
    proofs = conn.execute(
        """SELECT created_at, amount, status, image_path FROM school_payments
        WHERE school_code=? ORDER BY id DESC""",
        (school_code,),
    ).fetchall()
    proof_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            _esc(item[0]), item[1],
            "Rs %d pending for approval" % item[1] if item[2] == "PENDING" else "Approved",
            _proof_img(conn, item[3]),
        )
        for item in proofs
    )
    return (
        "<h1>School account</h1><p>Showing only " + _esc(school_code)
        + ". This khata updates by itself when an ID card job is created. Rate Rs %d per card.</p>"
        % CARD_RATE
        + "<table><tr><th>Date</th><th>Job</th><th>Detail</th><th>Cards</th><th>Rate</th><th>Amount</th></tr>"
        + body + "</table>"
        + "<h2>Payments</h2><table><tr><th>Date</th><th>Amount</th><th>Status</th><th>Screenshot</th></tr>"
        + proof_rows + "</table>"
        + '<h2>Send PhonePe proof</h2><form method="post" enctype="multipart/form-data">'
        + '<input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
        + '<input type="hidden" name="action" value="payment">'
        + '<label>Amount paid, Rs</label><input name="amount" inputmode="numeric" required>'
        + '<label>Payment screenshot</label><input name="proof" type="file" accept="image/jpeg,image/png" required>'
        + '<button type="submit">Upload screenshot</button></form>'
        + "<h2>Balance due</h2><p>Rs %d</p>" % due
        + "<p>Pending Rs %d is not deducted until Saini approves it. Charges Rs %d. Approved Rs %d.</p>"
        % (pending, charges, approved)
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


def save_shipping(conn, school_code, recipient, mobile, address, mode):
    ensure_orders(conn)
    _guard_school(conn, school_code)
    recipient = " ".join(str(recipient or "").split())
    address = " ".join(str(address or "").split())
    mode = (mode or "").strip()
    digits = "".join(ch for ch in str(mobile or "") if ch.isdigit())
    if len(recipient) < 2 or len(recipient) > 80:
        raise ValueError("Enter the recipient name")
    if len(digits) != 10:
        raise ValueError("Enter a 10 digit mobile number")
    if len(address) < 10 or len(address) > 200:
        raise ValueError("Enter the full address")
    if mode not in ("By hand", "Courier"):
        raise ValueError("Choose by hand or courier")
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    conn.execute(
        """INSERT INTO school_shipping
        (school_code, recipient, mobile, address, mode, confirmed_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(school_code) DO UPDATE SET
        recipient=excluded.recipient, mobile=excluded.mobile, address=excluded.address,
        mode=excluded.mode, confirmed_at=excluded.confirmed_at""",
        (school_code, recipient, digits, address, mode, _now()),
    )
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if before != after:
        conn.rollback()
        raise ValueError("Refused")
    conn.commit()
    return recipient


def shipping_block(conn, school_code, token):
    ensure_orders(conn)
    row = conn.execute(
        "SELECT recipient, mobile, address, mode, confirmed_at FROM school_shipping WHERE school_code=?",
        (school_code,),
    ).fetchone()
    current = (
        "<p class=\"bad\">No shipping address yet. Saini cannot start printing.</p>"
        if row is None
        else "<p class=\"ok\">Confirmed %s. %s, %s. %s. %s.</p>"
        % (_esc(row[4]), _esc(row[0]), _esc(row[1]), _esc(row[3]), _esc(row[2]))
    )
    return (
        current
        + '<form method="post">'
        + '<input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
        + '<input type="hidden" name="action" value="shipping">'
        + '<label>Recipient</label><input name="recipient" required maxlength="80">'
        + '<label>Mobile</label><input name="mobile" required inputmode="numeric" maxlength="10">'
        + '<label>Full address</label><input name="address" required maxlength="200">'
        + '<label>Mode</label><select name="mode"><option>By hand</option><option>Courier</option></select>'
        + '<button type="submit">Confirm address</button></form>'
        + "<p>Printing stays closed until this address is confirmed. The school cannot start printing.</p>"
    )


def advance_order(conn, order_id, action, mode="", note=""):
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
        if target == "PRINTING":
            ready = conn.execute(
                "SELECT 1 FROM school_shipping WHERE school_code=?",
                (row[1],),
            ).fetchone()
            if ready is None:
                raise ValueError("School has not confirmed the shipping address")
        if target == "DISPATCHED":
            mode = (mode or "").strip()
            note = " ".join(str(note or "").split())
            if mode not in ("By hand", "Courier"):
                raise ValueError("Choose by hand or courier")
            if len(note) < 2 or len(note) > 80:
                raise ValueError("Enter the person name or tracking number")
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
    if target == "DISPATCHED":
        conn.execute(
            "INSERT INTO school_dispatch (order_id, mode, note, created_at) VALUES (?,?,?,?)",
            (order_id, mode, note, _now()),
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
        """SELECT o.job_code, o.want_cards, o.want_marksheets, o.want_papers, o.status, o.created_at,
        IFNULL(d.mode, ''), IFNULL(d.note, '')
        FROM school_delivery_orders o
        LEFT JOIN school_dispatch d ON d.order_id=o.id
        WHERE o.school_code=? ORDER BY o.id DESC""",
        (school_code,),
    ).fetchall()
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            _esc(row[0]), _yes(row[1]), _yes(row[2]), _yes(row[3]),
            _esc(SCHOOL_LABEL.get(row[4], row[4])), _esc(row[5]),
            _esc((row[6] + " " + row[7]).strip()),
        )
        for row in rows
    )
    return (
        "<h2>Delivery jobs</h2><table><tr><th>Job</th><th>ID cards</th><th>Marksheets</th>"
        "<th>Papers</th><th>Stage</th><th>Time</th><th>Dispatch</th></tr>" + body + "</table>"
        + "<p>Saini prints, checks, packs, and dispatches. The school can see the stage but cannot change it.</p>"
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
        + '<p class="noprint"><button type="button" onclick="window.print()">Print shop sheet</button> '
        + '<a href="/saini-queue?sheet=' + str(order_id) + '">Print A4, 2 x 5</a></p>'
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


def _dispatch_form(token, order_id):
    return (
        '<form method="post">'
        + '<input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
        + '<input type="hidden" name="order_id" value="' + str(order_id) + '">'
        + '<input type="hidden" name="action" value="next">'
        + '<select name="dispatch_mode"><option>By hand</option><option>Courier</option></select>'
        + '<input name="dispatch_note" maxlength="80" required placeholder="Person or tracking">'
        + '<button type="submit">Dispatch</button></form>'
    )


def _batch_sheet(conn, order_id):
    row = conn.execute(
        "SELECT job_code, school_code, want_cards FROM school_delivery_orders WHERE id=?",
        (order_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Job not found")
    if not row[2]:
        raise ValueError("This job has no ID cards")
    school = conn.execute(
        "SELECT school_name, city FROM school_accounts WHERE school_code=?",
        (row[1],),
    ).fetchone()
    slots = conn.execute(
        """SELECT position, student_uid, class_name, student_name
        FROM school_delivery_slots WHERE order_id=? ORDER BY position""",
        (order_id,),
    ).fetchall()
    if not slots or len(slots) % 10:
        raise ValueError("A4 batch needs 10, 20, or 30 card positions")
    cards = []
    for position, uid, class_name, student_name in slots:
        extra = conn.execute(
            "SELECT father_name, photo_path FROM school_students WHERE school_code=? AND student_uid=?",
            (row[1], uid),
        ).fetchone()
        father = extra[0] if extra else ""
        photo = extra[1] if extra else ""
        place = ((position - 1) % 10) + 1
        cards.append(
            '<article class="card"><div class="top"><b>%s</b><span>%s</span></div>'
            '<div class="mid">%s<div><b>%s</b><br>Father: %s<br>Class %s<br>%s</div></div>'
            '<div class="foot">%s &nbsp; Place %d</div></article>'
            % (
                _esc(school[0] if school else row[1]),
                _esc(row[0]),
                _face(conn, row[1], uid, photo),
                _esc(student_name),
                _esc(father),
                _esc(class_name),
                _esc(uid),
                _esc(school[1] if school else ""),
                place,
            )
        )
    pages = []
    total_sheets = len(cards) // 10
    for number in range(total_sheets):
        chunk = "".join(cards[number * 10:(number + 1) * 10])
        pages.append(
            '<section class="sheet"><p class="noprint">Sheet %d of %d</p><div class="grid">%s</div></section>'
            % (number + 1, total_sheets, chunk)
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>A4 '
        + _esc(row[0]) + '</title><style>'
        '@page{size:A4 portrait;margin:8mm}'
        'body{font-family:Arial,sans-serif;margin:0;color:#172033}'
        '.sheet{page-break-after:always}'
        '.grid{display:grid;grid-template-columns:85mm 85mm;grid-auto-rows:54mm;gap:2mm}'
        '.card{border:0.4mm solid #17365d;box-sizing:border-box;padding:2mm;overflow:hidden}'
        '.top,.foot{display:flex;justify-content:space-between;font-size:9px}'
        '.mid{display:flex;gap:2mm;margin-top:1mm;font-size:11px}'
        'img.face{width:22mm;height:28mm;object-fit:cover}'
        '.noprint a,button{font-size:14px}'
        '@media print{.noprint{display:none}}'
        '</style></head><body><p class="noprint"><a href="/saini-queue?job='
        + str(order_id) + '">Back to job</a> '
        '<button type="button" onclick="window.print()">Print 2 x 5</button></p>'
        + "".join(pages) + '</body></html>'
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
                action = request.form.get("action", "")
                if action == "approve_payment":
                    paid = approve_payment(conn, int(request.form.get("payment_id", "0")))
                    notice = "Payment approved. Rs %d deducted from the school balance." % paid
                else:
                    target = advance_order(
                        conn, int(request.form.get("order_id", "0")), action,
                        request.form.get("dispatch_mode", ""),
                        request.form.get("dispatch_note", ""),
                    )
                    notice = "Job moved to " + SCHOOL_LABEL.get(target, target)
            except ValueError as exc:
                error = str(exc)
        session["saini_queue_csrf"] = secrets.token_hex(16)
        token = session["saini_queue_csrf"]
    sheet_text = (request.args.get("sheet") or "").strip()
    if request.method == "GET" and sheet_text.isdigit():
        try:
            return _batch_sheet(conn, int(sheet_text))
        except ValueError as exc:
            error = str(exc)
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
        if row[6] == "PACKED":
            action = _dispatch_form(token, row[0])
        elif row[6] in NEXT_LABEL:
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
    waiting = conn.execute(
        """SELECT id, school_code, amount, created_at, image_path
        FROM school_payments WHERE status='PENDING' ORDER BY id"""
    ).fetchall()
    pay_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>Rs %d pending for approval</td><td>%s</td><td>"
        % (_esc(item[1]), _esc(item[3]), item[2], _proof_img(conn, item[4]))
        + '<form method="post"><input type="hidden" name="csrf_token" value="%s">'
        % _esc(token)
        + '<input type="hidden" name="action" value="approve_payment">'
        + '<input type="hidden" name="payment_id" value="%d">' % item[0]
        + '<button type="submit">Approve</button></form></td></tr>'
        for item in waiting
    ) or '<tr><td colspan="5">No payment is waiting.</td></tr>'
    pay_table = (
        "<h2>Payments waiting</h2><table><tr><th>School</th><th>Time</th><th>Status</th><th>Screenshot</th><th></th></tr>"
        + pay_rows + "</table>"
    )
    flag = ('<p class="bad">%s</p>' % _esc(error)) if error else ""
    flag += ('<p class="ok">%s</p>' % _esc(notice)) if notice else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Saini delivery queue</title><style>'
        "body{font-family:Arial,sans-serif;max-width:980px;margin:24px auto;padding:16px;background:#f5f7fa;color:#172033}"
        "main{background:#fff;border:1px solid #d8dee9;border-radius:12px;padding:22px}"
        "table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:7px;vertical-align:top}"
        "button,select,input{background:#17365d;color:#fff;border:0;border-radius:8px;padding:8px 12px;width:auto}"
        "select,input{background:#fff;color:#172033;border:1px solid #d8dee9;margin:0 6px 6px 0}"
        ".ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"
        "</style></head><body><main><p><a href=\"/\">Home</a></p><h1>Central production queue</h1>"
        "<p>Saini accepts, prints, checks, packs, and dispatches. Schools only request. Nothing is activated.</p>"
        + filters + flag + pay_table
        + "<table><tr><th>Job</th><th>School</th><th>Cards</th><th>Marksheets</th><th>Papers</th><th>Stage</th><th>Time</th><th>Next</th></tr>"
        + body + "</table></main></body></html>"
    )
