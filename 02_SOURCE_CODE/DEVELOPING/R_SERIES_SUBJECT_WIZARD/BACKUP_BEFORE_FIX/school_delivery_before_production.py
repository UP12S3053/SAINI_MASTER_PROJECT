import hmac
import secrets
from datetime import datetime

import school_registry

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


def ensure_orders(conn):
    school_registry.assert_development_db(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_delivery_orders (
        id INTEGER PRIMARY KEY, school_code TEXT NOT NULL,
        want_cards INTEGER NOT NULL, want_marksheets INTEGER NOT NULL,
        want_papers INTEGER NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"""
    )
    conn.commit()


def save_order(conn, school_code, cards, sheets, papers):
    ensure_orders(conn)
    flags = (1 if cards else 0, 1 if sheets else 0, 1 if papers else 0)
    if sum(flags) == 0:
        raise ValueError("Choose ID cards, marksheets, or exam papers")
    row = conn.execute(
        "SELECT status, activated FROM school_accounts WHERE school_code=?",
        (school_code,),
    ).fetchone()
    if row is None or row[1] != 0 or row[0] != "DRAFT":
        raise ValueError("Only a DRAFT school can send a request")
    conn.execute(
        """INSERT INTO school_delivery_orders
        (school_code, want_cards, want_marksheets, want_papers, status, created_at)
        VALUES (?,?,?,?,'REQUESTED',?)""",
        (school_code, flags[0], flags[1], flags[2], _now()),
    )
    conn.commit()
    return school_code


def mark_dispatched(conn, order_id):
    ensure_orders(conn)
    before = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    changed = conn.execute(
        """UPDATE school_delivery_orders SET status='DISPATCHED'
        WHERE id=? AND status='REQUESTED'""",
        (order_id,),
    ).rowcount
    after = conn.execute("SELECT COUNT(*) FROM school_accounts WHERE activated!=0").fetchone()[0]
    if changed != 1 or before != after:
        conn.rollback()
        raise ValueError("Order is not open")
    conn.commit()
    return order_id


def orders_table(conn, school_code):
    ensure_orders(conn)
    rows = conn.execute(
        """SELECT want_cards, want_marksheets, want_papers, status, created_at
        FROM school_delivery_orders WHERE school_code=? ORDER BY id DESC""",
        (school_code,),
    ).fetchall()
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % ("YES" if row[0] else "NO", "YES" if row[1] else "NO", "YES" if row[2] else "NO", _esc(row[3]), _esc(row[4]))
        for row in rows
    )
    return (
        "<h2>Requests sent</h2><table><tr><th>ID cards</th><th>Marksheets</th><th>Papers</th><th>Status</th><th>Time</th></tr>"
        + body + "</table>"
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
                notice = "Dispatched order " + str(mark_dispatched(conn, int(request.form.get("order_id", "0"))))
            except ValueError:
                error = "Order is not open"
        session["saini_queue_csrf"] = secrets.token_hex(16)
        token = session["saini_queue_csrf"]
    rows = conn.execute(
        """SELECT id, school_code, want_cards, want_marksheets, want_papers, status, created_at
        FROM school_delivery_orders ORDER BY id DESC"""
    ).fetchall()
    body = "".join(
        "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>"
        % (row[0], _esc(row[1]), "YES" if row[2] else "NO", "YES" if row[3] else "NO", "YES" if row[4] else "NO", _esc(row[5]), _esc(row[6]))
        for row in rows
    )
    flag = ('<p class="bad">%s</p>' % _esc(error)) if error else ""
    flag += ('<p class="ok">%s</p>' % _esc(notice)) if notice else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Saini delivery queue</title><style>'
        "body{font-family:Arial,sans-serif;max-width:900px;margin:24px auto;padding:16px;background:#f5f7fa;color:#172033}"
        "main{background:#fff;border:1px solid #d8dee9;border-radius:12px;padding:22px}"
        "table{width:100%;border-collapse:collapse}td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:7px}"
        "button,input{box-sizing:border-box;width:100%;padding:10px;margin-top:6px;font-size:16px}"
        "button{background:#17365d;color:#fff;border:0;border-radius:8px}"
        ".ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"
        "</style></head><body><main><p><a href=\"/\">Home</a></p><h1>Saini delivery queue</h1>"
        "<p>Control stays with Saini. Schools only request. Nothing is activated.</p>"
        + flag
        + "<table><tr><th>ID</th><th>School</th><th>Cards</th><th>Marksheets</th><th>Papers</th><th>Status</th><th>Time</th></tr>"
        + body + "</table>"
        + '<form method="post"><input type="hidden" name="csrf_token" value="' + _esc(token) + '">'
        + '<label>Order ID</label><input name="order_id" required>'
        + '<button type="submit">Mark dispatched</button></form></main></body></html>'
    )
