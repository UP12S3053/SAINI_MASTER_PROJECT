import hashlib
import hmac
import secrets

import school_registry


PORTAL_PATHS = ("/school-login", "/school-logout", "/portal")


def password_matches(stored, password):
    if not isinstance(password, str) or not password.isascii():
        return False
    parts = str(stored).split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        rounds = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = parts[3]
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, rounds
        ).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


def _esc(value):
    text = str(value)
    return (
        text.replace("&", "&" + "amp;")
        .replace("<", "&" + "lt;")
        .replace(">", "&" + "gt;")
        .replace('"', "&" + "quot;")
    )


def _find_school(conn, code, password):
    school_registry.assert_development_db(conn)
    school_registry.ensure_schema(conn)
    code = (code or "").strip().upper()
    row = conn.execute(
        """SELECT school_code, school_name, city, password_hash, status, activated
        FROM school_accounts WHERE school_code=?""",
        (code,),
    ).fetchone()
    dummy = "pbkdf2_sha256$200000$" + ("ab" * 16) + "$" + ("cd" * 32)
    if row is None:
        password_matches(dummy, password or "invalid")
        return None
    if not password_matches(row[3], password or ""):
        return None
    return row


def portal_login(get_db, request, session):
    from flask import redirect

    error = ""
    token = session.get("portal_csrf") or secrets.token_hex(16)
    session["portal_csrf"] = token
    if request.method == "POST":
        posted = request.form.get("csrf_token", "")
        if not posted or not hmac.compare_digest(posted, token):
            error = "Security token expired. Reload the page."
        else:
            row = _find_school(
                get_db(),
                request.form.get("school_code", ""),
                request.form.get("password", ""),
            )
            if row is None:
                error = "School code or password is wrong."
            else:
                session["portal_school"] = row[0]
                session["portal_csrf"] = secrets.token_hex(16)
                return redirect("/portal")
    return _page(
        "School Portal Login",
        """<p class="ok">DEVELOPMENT ONLY. This login is separate from the paper-system password. A school stays DRAFT and cannot open papers or printing.</p>
%s
<form method="post" action="/school-login">
<input type="hidden" name="csrf_token" value="%s">
<label>School code</label><input name="school_code" required maxlength="12">
<label>Password</label><input name="password" type="password" required>
<button type="submit">School login</button>
</form>"""
        % (
            ('<p class="bad">%s</p>' % _esc(error)) if error else "",
            _esc(token),
        ),
    )


def portal_home(get_db, request, session):
    from flask import redirect

    code = session.get("portal_school")
    if not code:
        return redirect("/school-login")
    conn = get_db()
    school_registry.assert_development_db(conn)
    row = conn.execute(
        """SELECT school_code, school_name, city, status, activated
        FROM school_accounts WHERE school_code=?""",
        (code,),
    ).fetchone()
    if row is None:
        session.pop("portal_school", None)
        return redirect("/school-login")
    token = secrets.token_hex(16)
    session["portal_csrf"] = token
    activated = "NO" if row[4] == 0 else "YES"
    return _page(
        "School Portal",
        """<p class="ok">Signed in as %s. School records and ID card PDFs are open.</p>
<p><a href="/portal/data">School data</a></p>
<table><tr><th>Code</th><td>%s</td></tr>
<tr><th>Name</th><td>%s</td></tr>
<tr><th>City</th><td>%s</td></tr>
<tr><th>Status</th><td>%s</td></tr>
<tr><th>Activated</th><td>%s</td></tr></table>
<p><a href="/portal/records">School records and ID card PDFs</a></p>
<form method="post" action="/school-logout">
<input type="hidden" name="csrf_token" value="%s">
<button type="submit">School logout</button>
</form>"""
        % (
            _esc(row[0]),
            _esc(row[0]),
            _esc(row[1]),
            _esc(row[2]),
            _esc(row[3]),
            activated,
            _esc(token),
        ),
    )


def portal_logout(session, request):
    from flask import redirect

    posted = request.form.get("csrf_token", "")
    saved = session.get("portal_csrf", "")
    if posted and saved and hmac.compare_digest(posted, saved):
        session.pop("portal_school", None)
        session.pop("portal_csrf", None)
    return redirect("/school-login")


def _page(title, body):
    return """<!doctype html>
<html><head><meta charset="utf-8"><title>%s</title>
<style>
body{font-family:Arial,sans-serif;max-width:760px;margin:30px auto;padding:18px;background:#f5f7fa;color:#172033}
main{background:white;border:1px solid #d8dee9;border-radius:12px;padding:24px}
label{display:block;font-weight:bold;margin-top:14px}input,button{box-sizing:border-box;width:100%%;padding:11px;margin-top:6px;font-size:16px}
button{background:#17365d;color:white;border:0;border-radius:8px}
.ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}
table{width:100%%;border-collapse:collapse;margin-top:12px}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px}
</style></head><body><main>
<p><a href="/">Home</a></p>
<h1>%s</h1>
%s
</main></body></html>""" % (_esc(title), _esc(title), body)
