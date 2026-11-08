import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS school_accounts (
    id INTEGER PRIMARY KEY,
    school_code TEXT NOT NULL UNIQUE,
    school_name TEXT NOT NULL,
    city TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    activated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
"""


def assert_development_db(conn):
    row = conn.execute("PRAGMA database_list").fetchone()
    path = Path(row[2]).resolve()
    if path.parent.name != "DEVELOPMENT_SUBJECT_WIZARD":
        raise RuntimeError("REFUSED: school registry can write only the development database")


def ensure_schema(conn):
    assert_development_db(conn)
    conn.execute(SCHEMA)
    conn.commit()


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return "pbkdf2_sha256$200000$" + salt.hex() + "$" + digest.hex()


def suggest_code(school_name, city, existing):
    words = re.findall(r"[A-Za-z0-9]+", school_name + " " + city)
    base = "".join(word[0] for word in words).upper()[:8] or "SCH"
    code = base
    number = 1
    while code in existing:
        code = base + str(number)
        number += 1
    return code


def create_school(conn, school_name, city, school_code, password):
    assert_development_db(conn)
    ensure_schema(conn)
    school_name = " ".join(school_name.split())
    city = " ".join(city.split())
    if len(school_name) < 3 or len(city) < 2:
        raise ValueError("School name and city are required")
    if not password.isascii() or len(password) < 8:
        raise ValueError("Password must be at least 8 English letters or digits")
    existing = {row[0] for row in conn.execute("SELECT school_code FROM school_accounts")}
    code = (school_code or "").strip().upper() or suggest_code(school_name, city, existing)
    if not re.fullmatch(r"[A-Z0-9]{3,12}", code):
        raise ValueError("School code must be 3 to 12 letters or digits")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            """INSERT INTO school_accounts
            (school_code, school_name, city, password_hash, status, activated, created_at)
            VALUES (?,?,?,?, 'DRAFT', 0, ?)""",
            (code, school_name, city, hash_password(password), now),
        )
    except sqlite3.IntegrityError:
        raise ValueError("School code already exists: " + code)
    conn.commit()
    return code


def list_schools(conn):
    ensure_schema(conn)
    return conn.execute(
        """SELECT school_code, school_name, city, status, activated
        FROM school_accounts ORDER BY id"""
    ).fetchall()


def handle(get_db, request, session):
    conn = get_db()
    message = ""
    error = ""
    token = session.get("school_registry_csrf") or secrets.token_hex(16)
    session["school_registry_csrf"] = token
    if request.method == "POST":
        posted = request.form.get("csrf_token", "")
        if not posted or not hmac.compare_digest(posted, token):
            error = "Security token expired. Reload the page."
        else:
            try:
                code = create_school(
                    conn,
                    request.form.get("school_name", ""),
                    request.form.get("city", ""),
                    request.form.get("school_code", ""),
                    request.form.get("password", ""),
                )
                message = "Created " + code + " as DRAFT (inactive)."
                token = secrets.token_hex(16)
                session["school_registry_csrf"] = token
            except (ValueError, RuntimeError) as exc:
                error = str(exc)
    rows = list_schools(conn)
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (
            _esc(row[0]),
            _esc(row[1]),
            _esc(row[2]),
            _esc(row[3]),
            "NO" if row[4] == 0 else "YES",
        )
        for row in rows
    )
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>School Registration — DEVELOPMENT</title>
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}
main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}
label{display:block;font-weight:bold;margin-top:14px}input,button{box-sizing:border-box;width:100%%;padding:11px;margin-top:6px;font-size:16px}
button{background:#17365d;color:white;border:0;border-radius:8px}
.ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}
table{width:100%%;border-collapse:collapse;margin-top:12px}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px}
</style></head><body><main>
<p><a href="/">Home</a></p>
<h1>School Registration</h1>
<p class="ok">DEVELOPMENT ONLY. A school is saved as DRAFT and cannot log in yet. Papers, ID cards, and printing are unchanged.</p>
%s%s
<form method="post" action="/admin/schools">
<input type="hidden" name="csrf_token" value="%s">
<label>School name</label><input name="school_name" required>
<label>City</label><input name="city" required>
<label>School code, optional</label><input name="school_code" maxlength="12">
<label>Password</label><input name="password" type="password" required>
<button type="submit">Create DRAFT School</button>
</form>
<h2>Registered schools</h2>
<table><tr><th>Code</th><th>Name</th><th>City</th><th>Status</th><th>Activated</th></tr>%s</table>
</main></body></html>""" % (
        ('<p class="ok">%s</p>' % _esc(message)) if message else "",
        ('<p class="bad">%s</p>' % _esc(error)) if error else "",
        _esc(token),
        body,
    )


def _esc(value):
    text = str(value)
    amp = "&" + "amp;"
    lt = "&" + "lt;"
    gt = "&" + "gt;"
    quot = "&" + "quot;"
    return text.replace("&", amp).replace("<", lt).replace(">", gt).replace('"', quot)
