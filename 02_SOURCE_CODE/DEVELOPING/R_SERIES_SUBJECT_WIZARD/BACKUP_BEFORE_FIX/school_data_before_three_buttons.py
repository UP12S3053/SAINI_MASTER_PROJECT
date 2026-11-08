import hmac
import re
import secrets
from datetime import datetime

import school_registry


def ensure_schema(conn):
    school_registry.assert_development_db(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_classes (
        id INTEGER PRIMARY KEY,
        school_code TEXT NOT NULL,
        class_name TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (school_code, class_name)
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_students (
        id INTEGER PRIMARY KEY,
        school_code TEXT NOT NULL,
        class_name TEXT NOT NULL,
        student_name TEXT NOT NULL,
        father_name TEXT NOT NULL,
        mobile TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
        )"""
    )
    conn.commit()


def _esc(value):
    text = str(value)
    return (
        text.replace("&", "&" + "amp;")
        .replace("<", "&" + "lt;")
        .replace(">", "&" + "gt;")
        .replace('"', "&" + "quot;")
    )


def _clean_class(value):
    name = " ".join((value or "").split()).upper()
    if not re.fullmatch(r"[A-Z0-9-]{1,12}", name):
        raise ValueError("Class must be 1 to 12 letters or digits, such as UKG")
    return name


def _clean_person(value, label):
    name = " ".join((value or "").split())
    if len(name) < 2 or len(name) > 80 or "<" in name or ">" in name:
        raise ValueError(label + " is required")
    return name


def _clean_mobile(value):
    mobile = re.sub(r"\s+", "", value or "")
    if mobile and not re.fullmatch(r"[0-9]{10}", mobile):
        raise ValueError("Mobile must be 10 digits or blank")
    return mobile


def add_class(conn, school_code, class_name):
    ensure_schema(conn)
    name = _clean_class(class_name)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            "INSERT INTO school_classes (school_code, class_name, created_at) VALUES (?,?,?)",
            (school_code, name, now),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError("Class already exists: " + name)
        raise
    conn.commit()
    return name


def add_student(conn, school_code, class_name, student_name, father_name, mobile):
    ensure_schema(conn)
    class_name = _clean_class(class_name)
    owned = conn.execute(
        "SELECT 1 FROM school_classes WHERE school_code=? AND class_name=?",
        (school_code, class_name),
    ).fetchone()
    if owned is None:
        raise ValueError("Add this class for the logged-in school first")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO school_students
        (school_code, class_name, student_name, father_name, mobile, created_at)
        VALUES (?,?,?,?,?,?)""",
        (
            school_code,
            class_name,
            _clean_person(student_name, "Student name"),
            _clean_person(father_name, "Father name"),
            _clean_mobile(mobile),
            now,
        ),
    )
    conn.commit()


def classes_for(conn, school_code):
    ensure_schema(conn)
    return [
        row[0]
        for row in conn.execute(
            "SELECT class_name FROM school_classes WHERE school_code=? ORDER BY class_name",
            (school_code,),
        )
    ]


def students_for(conn, school_code):
    ensure_schema(conn)
    return list(
        conn.execute(
            """SELECT class_name, student_name, father_name, mobile
            FROM school_students WHERE school_code=? ORDER BY id""",
            (school_code,),
        )
    )


def handle(get_db, request, session):
    from flask import redirect

    school_code = session.get("portal_school")
    if not school_code:
        return redirect("/school-login")
    conn = get_db()
    school_registry.assert_development_db(conn)
    school = conn.execute(
        "SELECT school_code, status, activated FROM school_accounts WHERE school_code=?",
        (school_code,),
    ).fetchone()
    if school is None:
        session.pop("portal_school", None)
        return redirect("/school-login")
    error = ""
    notice = ""
    token = session.get("portal_data_csrf") or secrets.token_hex(16)
    session["portal_data_csrf"] = token
    if request.method == "POST":
        posted = request.form.get("csrf_token", "")
        if not posted or not hmac.compare_digest(posted, token):
            error = "Security token expired. Reload the page."
        else:
            try:
                action = request.form.get("action", "")
                if action == "class":
                    created = add_class(conn, school_code, request.form.get("class_name", ""))
                    notice = "Class saved: " + created
                elif action == "student":
                    add_student(
                        conn,
                        school_code,
                        request.form.get("class_name", ""),
                        request.form.get("student_name", ""),
                        request.form.get("father_name", ""),
                        request.form.get("mobile", ""),
                    )
                    notice = "Student saved for " + school_code + " only."
                else:
                    error = "Unknown action"
            except ValueError as exc:
                error = str(exc)
        session["portal_data_csrf"] = secrets.token_hex(16)
        token = session["portal_data_csrf"]
    class_names = classes_for(conn, school_code)
    students = students_for(conn, school_code)
    options = "".join("<option>%s</option>" % _esc(name) for name in class_names)
    rows = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (_esc(row[0]), _esc(row[1]), _esc(row[2]), _esc(row[3]))
        for row in students
    )
    flags = (
        ('<p class="bad">%s</p>' % _esc(error)) if error else ""
    ) + (('<p class="ok">%s</p>' % _esc(notice)) if notice else "")
    body = (
        '<p><a href="/portal">Portal</a></p><h1>School data</h1>'
        + '<p class="ok">Showing only %s. Status stays %s and Activated %s. Papers are not changed.</p>'
        % (_esc(school_code), _esc(school[1]), "NO" if school[2] == 0 else "YES")
        + flags
        + '<h2>Add class</h2><form method="post"><input type="hidden" name="csrf_token" value="%s">'
        % _esc(token)
        + '<input type="hidden" name="action" value="class"><label>Class</label>'
        + '<input name="class_name" required maxlength="12" placeholder="UKG">'
        + '<button type="submit">Save class</button></form>'
        + '<h2>Add student</h2><form method="post"><input type="hidden" name="csrf_token" value="%s">'
        % _esc(token)
        + '<input type="hidden" name="action" value="student"><label>Class</label><select name="class_name">'
        + options
        + "</select><label>Student name</label><input name=\"student_name\" required maxlength=\"80\">"
        + '<label>Father name</label><input name="father_name" required maxlength="80">'
        + '<label>Mobile, optional</label><input name="mobile" maxlength="10">'
        + '<button type="submit">Save student</button></form>'
        + "<h2>Students</h2><table><tr><th>Class</th><th>Student</th><th>Father</th><th>Mobile</th></tr>"
        + rows
        + "</table>"
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>School data</title><style>"
        "body{font-family:Arial,sans-serif;max-width:760px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}"
        "main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}"
        "label{display:block;font-weight:bold;margin-top:12px}"
        "input,select,button{box-sizing:border-box;width:100%;padding:10px;margin-top:6px;font-size:16px}"
        "button{background:#17365d;color:white;border:0;border-radius:8px}"
        "table{width:100%;border-collapse:collapse;margin-top:8px}"
        "td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px}"
        ".ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"
        "</style></head><body><main>"
        + body
        + "</main></body></html>"
    )
