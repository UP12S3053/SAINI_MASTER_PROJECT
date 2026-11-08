import base64
import hmac
import re
import secrets
from datetime import datetime
from pathlib import Path

import school_delivery
import school_registry

EXAMS = (
    ("Q", "Quarterly"),
    ("HY", "Half-yearly"),
    ("AN", "Annual"),
    ("M1", "First monthly"),
    ("M2", "Second monthly"),
    ("FN", "Final"),
)


def ensure_schema(conn):
    school_registry.assert_development_db(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_classes (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, class_name TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE (school_code, class_name))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_students (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, class_name TEXT NOT NULL,
        student_name TEXT NOT NULL, father_name TEXT NOT NULL,
        mobile TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_paper_needs (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, class_name TEXT NOT NULL,
        subject TEXT NOT NULL, student_strength INTEGER NOT NULL, max_marks REAL NOT NULL,
        created_at TEXT NOT NULL, UNIQUE (school_code, class_name, subject))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_marks (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL, student_uid TEXT NOT NULL,
        subject TEXT NOT NULL, exam_slot TEXT NOT NULL, obtained REAL NOT NULL,
        max_marks REAL NOT NULL, created_at TEXT NOT NULL,
        UNIQUE (school_code, student_uid, subject, exam_slot))"""
    )
    cols = {row[1] for row in conn.execute("PRAGMA table_info(school_students)")}
    for name, decl in (
        ("address", "TEXT NOT NULL DEFAULT ''"),
        ("photo_path", "TEXT NOT NULL DEFAULT ''"),
        ("student_uid", "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in cols:
            conn.execute("ALTER TABLE school_students ADD COLUMN " + name + " " + decl)
    conn.commit()


def _esc(value):
    text = str(value)
    return (
        text.replace("&", "&" + "amp;")
        .replace("<", "&" + "lt;")
        .replace(">", "&" + "gt;")
        .replace('"', "&" + "quot;")
    )


def _class_name(value):
    name = " ".join((value or "").split()).upper()
    if not re.fullmatch(r"[A-Z0-9-]{1,12}", name):
        raise ValueError("Class must be like UKG or 5")
    return name


def _subject(value):
    name = " ".join((value or "").split()).upper()
    if not re.fullmatch(r"[A-Z0-9-]{2,20}", name):
        raise ValueError("Subject must be like MATH or ENGLISH")
    return name


def _person(value, label):
    name = " ".join((value or "").split())
    if len(name) < 2 or len(name) > 80 or "<" in name or ">" in name:
        raise ValueError(label + " is required")
    return name


def _mobile(value):
    mobile = re.sub(r"\s+", "", value or "")
    if mobile and not re.fullmatch(r"[0-9]{10}", mobile):
        raise ValueError("Mobile must be 10 digits or blank")
    return mobile


def _address(value):
    text = " ".join((value or "").split())
    if len(text) > 120 or "<" in text or ">" in text:
        raise ValueError("Address is too long")
    return text


def _number(value, label, low, high, whole=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(label + " must be a number")
    if number < low or number > high:
        raise ValueError(label + " is out of range")
    return int(number) if whole else round(number, 2)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _remember_class(conn, school_code, class_name):
    conn.execute(
        """INSERT INTO school_classes (school_code, class_name, created_at)
        VALUES (?,?,?) ON CONFLICT(school_code, class_name) DO NOTHING""",
        (school_code, class_name, _now()),
    )


def save_paper(conn, school_code, class_name, subject, strength, max_marks):
    ensure_schema(conn)
    class_name = _class_name(class_name)
    subject = _subject(subject)
    strength = _number(strength, "Strength", 1, 500, True)
    max_marks = _number(max_marks, "Max marks", 1, 200)
    _remember_class(conn, school_code, class_name)
    conn.execute(
        """INSERT INTO school_paper_needs
        (school_code, class_name, subject, student_strength, max_marks, created_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(school_code, class_name, subject)
        DO UPDATE SET student_strength=excluded.student_strength, max_marks=excluded.max_marks""",
        (school_code, class_name, subject, strength, max_marks, _now()),
    )
    conn.commit()
    return class_name + " " + subject


def _photo_path(conn, school_code, uid):
    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent
    if root.name != "DEVELOPMENT_SUBJECT_WIZARD":
        raise ValueError("Photo folder refused")
    folder = (root / "school_photos" / school_code).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / (uid + ".jpg")).resolve()
    if folder not in path.parents:
        raise ValueError("Unsafe photo path")
    return path


def _read_photo(storage):
    if storage is None or not getattr(storage, "filename", ""):
        return b""
    data = storage.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError("Photo must be under 2 MB")
    if data and not (data.startswith(b"\xff\xd8") or data.startswith(b"\x89PNG")):
        raise ValueError("Photo must be JPG or PNG")
    return data


def save_student(conn, school_code, class_name, student_name, father_name, mobile, address, photo):
    ensure_schema(conn)
    class_name = _class_name(class_name)
    _remember_class(conn, school_code, class_name)
    data = _read_photo(photo)
    cur = conn.execute(
        """INSERT INTO school_students
        (school_code, class_name, student_name, father_name, mobile, address, created_at, student_uid)
        VALUES (?,?,?,?,?,?,?,?)""",
        (
            school_code, class_name, _person(student_name, "Student name"),
            _person(father_name, "Father name"), _mobile(mobile), _address(address), _now(), "",
        ),
    )
    uid = school_code + "-" + str(cur.lastrowid).zfill(4)
    rel = ""
    if data:
        path = _photo_path(conn, school_code, uid)
        path.write_bytes(data)
        rel = "school_photos/" + school_code + "/" + uid + ".jpg"
    conn.execute(
        "UPDATE school_students SET student_uid=?, photo_path=? WHERE id=? AND school_code=?",
        (uid, rel, cur.lastrowid, school_code),
    )
    conn.commit()
    return uid


def replace_photo(conn, school_code, uid, photo):
    ensure_schema(conn)
    uid = (uid or "").strip().upper()
    row = conn.execute(
        "SELECT id FROM school_students WHERE school_code=? AND student_uid=?",
        (school_code, uid),
    ).fetchone()
    if row is None:
        raise ValueError("Student not found for this school")
    data = _read_photo(photo)
    if not data:
        raise ValueError("Choose a photo")
    path = _photo_path(conn, school_code, uid)
    path.write_bytes(data)
    rel = "school_photos/" + school_code + "/" + uid + ".jpg"
    conn.execute(
        "UPDATE school_students SET photo_path=? WHERE school_code=? AND student_uid=?",
        (rel, school_code, uid),
    )
    conn.commit()
    return uid


def save_marks(conn, school_code, uid, subject, boxes):
    ensure_schema(conn)
    uid = (uid or "").strip().upper()
    subject = _subject(subject)
    student = conn.execute(
        "SELECT class_name FROM school_students WHERE school_code=? AND student_uid=?",
        (school_code, uid),
    ).fetchone()
    if student is None:
        raise ValueError("Student not found for this school")
    filled = [str(item or "").strip() for item in boxes]
    if len(filled) != 4:
        raise ValueError("Four mark boxes are required")
    used = [item != "" for item in filled]
    if used == [True, True, True, True]:
        plan = (("M1", "First monthly"), ("HY", "Half-yearly"), ("M2", "Second monthly"), ("AN", "Annual"))
    elif used == [True, True, True, False]:
        plan = (("Q", "Quarterly"), ("HY", "Half-yearly"), ("AN", "Annual"))
    else:
        raise ValueError("Fill the first 3 boxes, or all 4. Do not leave a gap.")
    cap = conn.execute(
        """SELECT max_marks FROM school_paper_needs
        WHERE school_code=? AND class_name=? AND subject=?""",
        (school_code, student[0], subject),
    ).fetchone()
    max_marks = cap[0] if cap else 100
    saved = []
    for index, (slot, label) in enumerate(plan):
        score = _number(filled[index], label, 0, max_marks)
        conn.execute(
            """INSERT INTO school_marks
            (school_code, student_uid, subject, exam_slot, obtained, max_marks, created_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(school_code, student_uid, subject, exam_slot)
            DO UPDATE SET obtained=excluded.obtained, max_marks=excluded.max_marks""",
            (school_code, uid, subject, slot, score, max_marks, _now()),
        )
        saved.append(label)
    conn.commit()
    return uid + " (" + ", ".join(saved) + ")"


def _rows(conn, sql, args):
    return list(conn.execute(sql, args))


def _img(path):
    file_path = Path(path) if path else None
    if not file_path or not file_path.is_file():
        return ""
    raw = file_path.read_bytes()
    kind = "png" if raw.startswith(b"\x89PNG") else "jpeg"
    return '<img alt="student photo" style="width:90px;height:120px;object-fit:cover" src="data:image/' + kind + ";base64," + base64.b64encode(raw).decode("ascii") + '">'


def handle(get_db, request, session):
    from flask import redirect

    school_code = session.get("portal_school")
    if not school_code:
        return redirect("/school-login")
    conn = get_db()
    school_registry.assert_development_db(conn)
    school = conn.execute(
        "SELECT status, activated FROM school_accounts WHERE school_code=?",
        (school_code,),
    ).fetchone()
    if school is None:
        session.pop("portal_school", None)
        return redirect("/school-login")
    ensure_schema(conn)
    error = ""
    notice = ""
    lookup = (request.values.get("student_uid") or "").strip().upper()
    token = session.get("portal_data_csrf") or secrets.token_hex(16)
    session["portal_data_csrf"] = token
    if request.method == "POST":
        posted = request.form.get("csrf_token", "")
        if not posted or not hmac.compare_digest(posted, token):
            error = "Security token expired. Reload the page."
        else:
            action = request.form.get("action", "")
            try:
                form = request.form
                if action == "paper":
                    notice = "Paper data saved: " + save_paper(
                        conn, school_code, form.get("class_name"), form.get("subject"),
                        form.get("strength"), form.get("max_marks"),
                    )
                elif action == "makepaper":
                    import online_paper
                    notice = online_paper.make_online_paper(
                        conn, school_code, form.get("class_name"), form.get("subject"), form.get("sheets"),
                    )
                elif action == "student":
                    notice = "ID card saved. Unique ID " + save_student(
                        conn, school_code, form.get("class_name"), form.get("student_name"),
                        form.get("father_name"), form.get("mobile"), form.get("address"),
                        request.files.get("photo"),
                    )
                elif action == "photo":
                    notice = "Photo updated for " + replace_photo(
                        conn, school_code, form.get("student_uid"), request.files.get("photo"),
                    )
                    lookup = form.get("student_uid", "").strip().upper()
                elif action == "marks":
                    notice = "Marks saved for " + save_marks(
                        conn, school_code, form.get("student_uid"), form.get("subject"),
                        [form.get("mark_1"), form.get("mark_2"), form.get("mark_3"), form.get("mark_4")],
                    )
                    lookup = form.get("student_uid", "").strip().upper()
                elif action == "shipping":
                    notice = "Address confirmed for " + school_delivery.save_shipping(
                        conn, school_code, form.get("recipient"), form.get("mobile"),
                        form.get("address"), form.get("mode"),
                    )
                elif action == "payment":
                    notice = school_delivery.save_payment(
                        conn, school_code, form.get("amount"), request.files.get("proof"),
                    )
                elif action == "cardsheet":
                    copies = [(key[5:], form.get(key)) for key in form if key.startswith("copy_")]
                    job_code, amount = school_delivery.save_card_job(
                        conn, school_code, copies, form.get("want_marksheets"), form.get("want_papers"),
                    )
                    notice = "A4 job " + job_code + " created. Account increased by Rs " + str(amount) + "."
                elif action == "order":
                    notice = "Request sent to Saini for " + school_delivery.save_order(
                        conn, school_code, form.get("want_cards"),
                        form.get("want_marksheets"), form.get("want_papers"),
                    )
                elif action == "join":
                    import production_queue
                    notice = production_queue.join_line(conn, school_code, form.get("kind"))
                else:
                    error = "Unknown action"
            except ValueError as exc:
                error = str(exc)
        session["portal_data_csrf"] = secrets.token_hex(16)
        token = session["portal_data_csrf"]
    part = ""
    if request.method == "POST":
        part = {"paper": "paper", "student": "id", "photo": "id", "marks": "result", "order": "output", "cardsheet": "output", "payment": "account", "shipping": "shipping", "join": "line", "makepaper": "paper"}.get(
            request.form.get("action", ""), ""
        )
    if not part:
        part = request.values.get("part", "")
    if part not in ("paper", "id", "result", "output", "account", "shipping", "line"):
        part = ""
    papers = _rows(
        conn,
        """SELECT class_name, subject, student_strength, max_marks
        FROM school_paper_needs WHERE school_code=? ORDER BY class_name, subject""",
        (school_code,),
    )
    students = _rows(
        conn,
        """SELECT student_uid, class_name, student_name, father_name, mobile, address, photo_path
        FROM school_students WHERE school_code=? ORDER BY id DESC LIMIT 12""",
        (school_code,),
    )
    root = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve().parent
    found = None
    marks = []
    if lookup:
        found = conn.execute(
            """SELECT student_uid, class_name, student_name, father_name, mobile, address, photo_path
            FROM school_students WHERE school_code=? AND student_uid=?""",
            (school_code, lookup),
        ).fetchone()
        if found:
            marks = _rows(
                conn,
                """SELECT subject, exam_slot, obtained, max_marks FROM school_marks
                WHERE school_code=? AND student_uid=? ORDER BY subject, exam_slot""",
                (school_code, lookup),
            )
        elif part == "result" and not error:
            error = "Student not found for this school"
    exam_options = "".join('<option value="%s">%s</option>' % (code, _esc(label)) for code, label in EXAMS)
    paper_rows = ""
    online_names = {"NUR", "NURSERY", "LKG", "UKG", "PREP", "I", "1", "1ST", "II", "2", "2ND"}
    for row in papers:
        cells = "".join("<td>%s</td>" % _esc(item) for item in row)
        if str(row[0]).upper() in online_names:
            action_cell = (
                '<a href="/paper?class_level=' + _esc(row[0]) + '&subject=' + _esc(row[1]) + '">Make paper</a>'
            )
        else:
            action_cell = "Class 3-12 stays on the old system"
        paper_rows += "<tr>" + cells + "<td>" + action_cell + "</td></tr>"
    student_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(row[0]), _esc(row[1]), _esc(row[2]), _esc(row[3]), _esc(row[4]))
        for row in students
    )
    mark_names = dict(EXAMS)
    mark_rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s / %s</td></tr>"
        % (_esc(row[0]), _esc(mark_names.get(row[1], row[1])), _esc(row[2]), _esc(row[3]))
        for row in marks
    )
    profile = ""
    if found:
        photo = _img(root / found[6]) if found[6] else ""
        profile = (
            "<p>" + photo + "</p><table>"
            + "".join(
                "<tr><th>%s</th><td>%s</td></tr>" % (label, _esc(found[index]))
                for index, label in (
                    (0, "Unique ID"), (1, "Class"), (2, "Student"), (3, "Father"), (4, "Mobile"), (5, "Address"),
                )
            )
            + "</table><h3>Marks already saved</h3><table><tr><th>Subject</th><th>Exam</th><th>Marks</th></tr>"
            + mark_rows + "</table>"
        )
    hidden = '<input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
    flags = ""
    if error:
        flags += '<p class="bad">' + _esc(error) + "</p>"
    if notice:
        flags += '<p class="ok">' + _esc(notice) + "</p>"
    head = (
        '<p><a href="/portal">Portal</a> | <a href="/portal/data">School data</a></p>'
        + "<h1>" + {"paper": "Paper data", "id": "ID card data", "result": "Result data", "output": "Final output", "account": "School account", "shipping": "Shipping address", "line": "Production line"}.get(part, "School data") + "</h1>"
        + '<p class="ok">Only ' + _esc(school_code) + ". Status " + _esc(school[0])
        + ". Activated " + ("NO" if school[1] == 0 else "YES") + ".</p>"
        + flags
    )
    if part == "paper":
        body = (
            head + '<form method="post">' + hidden
            + '<input type="hidden" name="action" value="paper">'
            + '<label>Class</label><input name="class_name" required maxlength="12" placeholder="UKG">'
            + '<label>Subject</label><input name="subject" required maxlength="20" placeholder="MATH">'
            + '<label>Students strength</label><input name="strength" required inputmode="numeric">'
            + '<label>Max marks</label><input name="max_marks" required inputmode="decimal">'
            + '<button type="submit">Save paper data</button></form>'
            + "<table><tr><th>Class</th><th>Subject</th><th>Strength</th><th>Max</th><th>Online paper</th></tr>" + paper_rows + "</table>"
        )
    elif part == "id":
        body = (
            head + '<form id="idform" method="post" enctype="multipart/form-data">' + hidden
            + '<input type="hidden" name="action" value="student">'
            + '<label>Class</label><input name="class_name" required maxlength="12" placeholder="UKG">'
            + '<label>Student name</label><input name="student_name" required maxlength="80">'
            + '<label>Father name</label><input name="father_name" required maxlength="80">'
            + '<label>Mobile</label><input name="mobile" maxlength="10">'
            + '<label>Address</label><input name="address" maxlength="120">'
            + '<label>Photo</label><input id="photo" name="photo" type="file" accept="image/jpeg,image/png">'
            + '<label>Crop zoom</label><input id="zoom" type="range" min="1" max="3" step="0.05" value="1">'
            + '<canvas id="cv" width="240" height="320"></canvas>'
            + '<button type="submit">Save ID card data</button></form>'
            + '<form method="post" enctype="multipart/form-data">' + hidden
            + '<input type="hidden" name="action" value="photo">'
            + '<label>Replace photo for Unique ID</label><input name="student_uid" maxlength="20" placeholder="BSM-0001">'
            + '<input name="photo" type="file" accept="image/jpeg,image/png">'
            + '<button type="submit">Update photo</button></form>'
            + "<table><tr><th>ID</th><th>Class</th><th>Student</th><th>Father</th><th>Mobile</th></tr>"
            + student_rows + "</table>"
            + "<script>var img=null,ready=false,cv=document.getElementById('cv'),box=document.getElementById('photo');"
            + "function draw(){if(!img)return;var z=+document.getElementById('zoom').value;var g=cv.getContext('2d');"
            + "var s=Math.max(cv.width/img.width,cv.height/img.height)*z;var w=img.width*s,h=img.height*s;"
            + "g.fillStyle='#fff';g.fillRect(0,0,cv.width,cv.height);g.drawImage(img,(cv.width-w)/2,(cv.height-h)/2,w,h);} "
            + "box.onchange=function(){var f=box.files[0];if(!f)return;img=new Image();img.onload=draw;img.src=URL.createObjectURL(f);};"
            + "document.getElementById('zoom').oninput=draw;document.getElementById('idform').onsubmit=function(e){"
            + "if(!img||ready)return true;e.preventDefault();cv.toBlob(function(b){var d=new DataTransfer();"
            + "d.items.add(new File([b],'photo.jpg',{type:'image/jpeg'}));box.files=d.files;ready=true;"
            + "document.getElementById('idform').submit();},'image/jpeg',0.85);};</script>"
        )
    elif part == "result":
        body = (
            head + profile
            + '<form method="get" action="/portal/data"><input type="hidden" name="part" value="result">'
            + '<label>Student unique ID</label><input name="student_uid" required maxlength="20" value="'
            + _esc(lookup) + '"><button type="submit">Show student</button></form>'
            + '<form method="post">' + hidden + '<input type="hidden" name="action" value="marks">'
            + '<input type="hidden" name="student_uid" value="' + _esc(lookup) + '">'
            + '<label>Class</label><input value="' + _esc(found[1] if found else '') + '" readonly>'
            + '<label>Subject</label><input name="subject" required maxlength="20" placeholder="MATH">'
            + '<p>Fill 3 boxes for Quarterly, Half-yearly, Annual. Fill all 4 for First monthly, Half-yearly, Second monthly, Annual.</p>'
            + '<label>Obtained marks 1</label><input name="mark_1" inputmode="decimal">'
            + '<label>Obtained marks 2</label><input name="mark_2" inputmode="decimal">'
            + '<label>Obtained marks 3</label><input name="mark_3" inputmode="decimal">'
            + '<label>Obtained marks 4, optional</label><input name="mark_4" inputmode="decimal">'
            + '<button type="submit">Save marks</button></form>'
        )
    elif part == "output":
        student_count = conn.execute(
            "SELECT COUNT(*) FROM school_students WHERE school_code=?", (school_code,)
        ).fetchone()[0]
        mark_count = conn.execute(
            "SELECT COUNT(*) FROM school_marks WHERE school_code=?", (school_code,)
        ).fetchone()[0]
        body = (
            head
            + "<p>Saini will prepare and deliver for " + _esc(school_code) + ". The school cannot print. Status stays DRAFT.</p>"
            + "<table><tr><th>Item</th><th>Count</th></tr>"
            + "<tr><td>Paper plans</td><td>" + str(len(papers)) + "</td></tr>"
            + "<tr><td>ID card students</td><td>" + str(student_count) + "</td></tr>"
            + "<tr><td>Result marks</td><td>" + str(mark_count) + "</td></tr></table>"
            + "<h2>Paper plans</h2><table><tr><th>Class</th><th>Subject</th><th>Strength</th><th>Max</th></tr>"
            + paper_rows + "</table>"
            + school_delivery.card_job_form(conn, school_code, token)
            + school_delivery.orders_table(conn, school_code)
        )
    elif part == "account":
        body = head + school_delivery.account_block(conn, school_code, token)
    elif part == "shipping":
        body = head + school_delivery.shipping_block(conn, school_code, token)
    elif part == "line":
        import production_queue
        body = head + production_queue.school_block(conn, school_code, token)
    else:
        body = (
            head
            + '<a class="go" href="/portal/data?part=paper">1. Paper data</a>'
            + '<a class="go" href="/portal/data?part=id">2. ID card data</a>'
            + '<a class="go" href="/portal/data?part=result">3. Result data</a>'
            + '<a class="go" href="/portal/data?part=output">4. Final output</a>'
            + '<a class="go" href="/portal/data?part=account">5. Account</a>'
            + '<a class="go" href="/portal/data?part=shipping">6. Shipping address</a>'
            + '<a class="go" href="/portal/data?part=line">7. Production line</a>'
        )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>School data</title><style>"
        "body{font-family:Arial,sans-serif;max-width:820px;margin:24px auto;padding:16px;background:#f5f7fa;color:#172033}"
        "main{background:#fff;border:1px solid #d8dee9;border-radius:12px;padding:22px}"
        "label{display:block;font-weight:bold;margin-top:10px}"
        "input,select,button{box-sizing:border-box;width:100%;padding:10px;margin-top:4px;font-size:16px}input[type=checkbox]{width:auto;margin-right:8px}"
        "button{background:#17365d;color:#fff;border:0;border-radius:8px}"
        "table{width:100%;border-collapse:collapse;margin:10px 0 18px}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:7px}"
        "h2{margin-top:28px;border-top:1px solid #d8dee9;padding-top:16px}"
        ".ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"
        "a.go{display:block;background:#17365d;color:#fff;text-align:center;text-decoration:none;padding:16px;margin-top:14px;border-radius:8px;font-size:18px}"
        "canvas{width:120px;height:160px;background:#eee;margin-top:8px}"
        "</style></head><body><main>" + body + "</main></body></html>"
    )
