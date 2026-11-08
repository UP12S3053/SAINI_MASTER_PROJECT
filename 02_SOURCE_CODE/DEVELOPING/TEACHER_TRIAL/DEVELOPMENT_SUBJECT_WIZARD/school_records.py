# -*- coding: utf-8 -*-
"""School teacher records. One school only: view, edit, delete, class-wise PDFs."""
import io
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw, ImageFont

EXCEL = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\student_data.xlsx")
OUTPUT = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\OUTPUT")
PHOTO_LIBRARY = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\PHOTO_LIBRARY")
MAX_CARDS = 200
CLASS_ORDER = [
    "PLAY", "NUR", "NURSERY", "LKG", "UKG",
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII",
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
]
EDITABLE = ("student_name", "class", "father_name", "mob_number", "address")


def _esc(value):
    text = str(value or "")
    return text.replace("&", "&").replace("<", "<").replace(">", ">")


def _school(session):
    return str(session.get("portal_school") or "").strip().upper()


def _header(sheet):
    return {
        str(cell.value or "").strip(): cell.column
        for cell in sheet[1]
        if str(cell.value or "").strip()
    }


def _rows(school):
    if not EXCEL.is_file():
        return []
    book = openpyxl.load_workbook(EXCEL, read_only=True, data_only=True)
    sheet = book.active
    header = [str(cell.value or "").strip() for cell in next(sheet.iter_rows(max_row=1))]
    wanted = {"student_unique_id", "student_name", "class", "father_name", "mob_number", "address", "school_code"}
    index = {name: header.index(name) for name in wanted if name in header}
    rows = []
    for number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        code = str(values[index["school_code"]] or "").strip().upper() if "school_code" in index else ""
        if code != school:
            continue
        name = str(values[index.get("student_name", 0)] or "").strip()
        if not name or name == ".":
            continue
        rows.append({
            "row": number,
            "student_unique_id": str(values[index.get("student_unique_id", 0)] or "").strip(),
            "student_name": name,
            "class": str(values[index.get("class", 0)] or "").strip(),
            "father_name": str(values[index.get("father_name", 0)] or "").strip(),
            "mob_number": str(values[index.get("mob_number", 0)] or "").strip(),
            "address": str(values[index.get("address", 0)] or "").strip(),
            "photo": str(values[index.get("STUDENT_PHOTO_PATH", 0)] or "").strip() if "STUDENT_PHOTO_PATH" in index else "",
        })
    book.close()
    rows.sort(key=lambda item: (_class_rank(item["class"]), item["student_name"]))
    return rows


def _class_rank(name):
    key = str(name or "").strip().upper()
    return CLASS_ORDER.index(key) if key in CLASS_ORDER else 99


def _save_edit(school, uid, form):
    book = openpyxl.load_workbook(EXCEL)
    sheet = book.active
    header = _header(sheet)
    uid_col = header.get("student_unique_id")
    school_col = header.get("school_code")
    if not uid_col or not school_col:
        raise ValueError("Excel columns missing")
    target = None
    for row in range(2, sheet.max_row + 1):
        if str(sheet.cell(row, uid_col).value or "").strip().upper() != uid:
            continue
        if str(sheet.cell(row, school_col).value or "").strip().upper() != school:
            continue
        target = row
        break
    if target is None:
        raise ValueError("This record is not in your school")
    for name in EDITABLE:
        column = header.get(name)
        if column:
            sheet.cell(target, column).value = str(form.get(name) or "").strip()
    book.save(EXCEL)
    book.close()


def _delete(school, uid):
    book = openpyxl.load_workbook(EXCEL)
    sheet = book.active
    header = _header(sheet)
    uid_col = header.get("student_unique_id")
    school_col = header.get("school_code")
    for row in range(2, sheet.max_row + 1):
        if str(sheet.cell(row, uid_col).value or "").strip().upper() != uid:
            continue
        if str(sheet.cell(row, school_col).value or "").strip().upper() != school:
            raise ValueError("Delete blocked: other school")
        sheet.delete_rows(row, 1)
        book.save(EXCEL)
        book.close()
        return
    book.close()
    raise ValueError("Record not found in your school")


def _images(school):
    folder = OUTPUT / school / "FRONT"
    if not folder.is_dir():
        return []
    return [path for path in folder.glob("*.png") if path.is_file() and path.stat().st_size > 0]


def _ordered(school, latest):
    images = _images(school)
    if not images:
        raise ValueError("Is school ke ID card abhi nahi bane")
    by_uid = {item["student_unique_id"].upper(): item for item in _rows(school)}
    if latest:
        newest = max(path.stat().st_mtime for path in images)
        images = [path for path in images if newest - path.stat().st_mtime <= 6 * 3600]
    cards = []
    for path in images:
        row = by_uid.get(path.stem.upper(), {})
        cards.append((path, row, str(row.get("class") or "OTHER").upper()))
    cards.sort(key=lambda item: (_class_rank(item[2]), str(item[1].get("student_name") or item[0].stem)))
    return cards


def _parts(cards):
    return [cards[start:start + MAX_CARDS] for start in range(0, len(cards), MAX_CARDS)] or [[]]


def _pdf(cards):
    pages = []
    for path, row, klass in cards:
        pages.append(_one_card(path, row, klass))
    if not pages:
        raise ValueError("PDF ke liye card nahi mile")
    buffer = io.BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=150)
    buffer.seek(0)
    return buffer


def _one_card(path, row, klass):
    card = Image.open(path).convert("RGB")
    page = Image.new("RGB", card.size, "white")
    page.paste(card, (0, 0))
    return page


def _card_path(school, uid, photo=""):
    uid = str(uid or "").strip()
    names = []
    if photo:
        names.append(Path(photo))
    if uid:
        names.extend([
            PHOTO_LIBRARY / school / (uid + ".jpg"),
            PHOTO_LIBRARY / school / (uid + ".jpeg"),
            PHOTO_LIBRARY / school / (uid + ".png"),
            OUTPUT / school / "FRONT" / (uid + ".png"),
            OUTPUT / school / "FRONT" / (uid + ".jpg"),
        ])
    for path in names:
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _find(rows, uid):
    uid = str(uid or "").strip().upper()
    for row in rows:
        if row["student_unique_id"].upper() == uid:
            return row
    return None


def _links(kind, parts):
    if not parts or not parts[0]:
        return ""
    links = []
    label = "Latest ID card PDF" if kind == "latest" else "All ID cards PDF"
    for number in range(1, len(parts) + 1):
        links.append(
            '<a class="pdfbtn" href="/portal/records/pdf/%s?part=%s">%s part %s (%s cards)</a>' % (
                kind, number, label, number, len(parts[number - 1])
            )
        )
    return " ".join(links)


def _page(school, rows, notice, error, latest_parts, all_parts, found):
    body = []
    if notice:
        body.append('<p class="ok">' + _esc(notice) + "</p>")
    if error:
        body.append('<p class="bad">' + _esc(error) + "</p>")
    body.append("<p><a href=\"/portal\">Portal</a> | School <b>" + _esc(school) + "</b> | Records " + str(len(rows)) + "</p>")
    body.append(
        "<form method=\"get\" class=\"lookup\"><label>Student ID</label>"
        "<input name=\"id\" placeholder=\"BSM3014\" required>"
        "<button>Show record</button></form>"
    )
    if found:
        uid = _esc(found["student_unique_id"])
        picture = ""
        if uid and _card_path(school, found["student_unique_id"], found.get("photo", "")):
            picture = "<img src=\"/portal/records/card/" + uid + "\" alt=\"ID card\">"
        body.append(
            "<section class=\"cardbox\">" + picture
            + "<div><h2>" + uid + "</h2><p>" + _esc(found["student_name"]) + " | " + _esc(found["class"]) + "</p>"
            "<p>Father: " + _esc(found["father_name"]) + "</p>"
            "<p>Mobile: " + _esc(found["mob_number"]) + "</p>"
            "<p>Address: " + _esc(found["address"]) + "</p>"
            "<p><a href=\"/portal/records?edit=" + uid + "\">Edit this record</a></p></div></section>"
        )
    body.append("<p>Latest ID card PDF: " + (_links("latest", latest_parts) or "abhi nahi") + "</p>")
    body.append("<p>All ID cards, class wise, max 200 per file: " + (_links("all", all_parts) or "abhi nahi") + "</p>")
    body.append("<table><tr><th>ID</th><th>Name</th><th>Class</th><th>Father</th><th>Mobile</th><th>Address</th><th></th></tr>")
    for row in rows:
        uid = _esc(row["student_unique_id"])
        body.append(
            "<tr><td>" + uid + "</td><td>" + _esc(row["student_name"]) + "</td><td>" + _esc(row["class"])
            + "</td><td>" + _esc(row["father_name"]) + "</td><td>" + _esc(row["mob_number"])
            + "</td><td>" + _esc(row["address"]) + '</td><td><a href="/portal/records?id=' + uid + '">Open</a></td></tr>'
        )
    body.append("</table>")
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>" + _esc(school) + " records</title><style>"
        "body{font-family:Arial,sans-serif;margin:0;background:#f4f7fb;color:#172033}"
        "main{max-width:1100px;margin:0 auto;padding:16px}"
        "table{width:100%;border-collapse:collapse;background:white}"
        "td,th{border-bottom:1px solid #d8dee9;text-align:left;padding:8px;font-size:14px}"
        "a{color:#17365d}.ok{background:#e7f6ec;padding:10px;border-radius:8px}.bad{background:#fde8e8;padding:10px;border-radius:8px}"
        "form{background:white;padding:14px;border-radius:10px;margin:14px 0}"
        "label{display:block;font-weight:bold;margin-top:10px}"
        "input{display:block;width:100%;max-width:420px;box-sizing:border-box;padding:10px;margin:4px 0 8px;font-size:16px}"
        "button{background:#17365d;color:white;border:0;border-radius:6px;padding:10px 16px;font-size:15px}"
        ".cardbox{display:flex;gap:16px;background:white;padding:14px;border-radius:12px;align-items:flex-start}"
        ".cardbox img{width:280px;max-width:100%;border:1px solid #d8dee9;background:#fff}"
        ".editbox{display:flex;gap:16px;align-items:flex-start}"
        ".editphoto{width:240px;max-width:100%;border:1px solid #d8dee9;background:#fff}"
        "</style></head><body><main><h1>School records</h1>" + "".join(body) + "</main></body></html>"
    )


def _edit_form(school, row, token):
    fields = []
    for name, label in (
        ("student_name", "Name"), ("class", "Class"), ("father_name", "Father"),
        ("mob_number", "Mobile"), ("address", "Address"),
    ):
        fields.append("<label>" + label + "</label><input name=\"" + name + "\" value=\"" + _esc(row.get(name)) + "\">")
    uid = _esc(row["student_unique_id"])
    photo = ""
    if uid and _card_path(school, row["student_unique_id"], row.get("photo", "")):
        photo = "<img class=\"editphoto\" src=\"/portal/records/card/" + uid + "\" alt=\"student photo\">"
    return (
        "<form method=\"post\" class=\"editbox\">" + photo
        + "<div><input type=\"hidden\" name=\"csrf_token\" value=\"" + _esc(token) + "\">"
        "<input type=\"hidden\" name=\"action\" value=\"save\"><input type=\"hidden\" name=\"uid\" value=\"" + uid + "\">"
        "<p>Editing <b>" + (uid or "this record") + "</b>. School code cannot be changed.</p>"
        + "".join(fields) + "<button>Save</button></div></form>"
        "<form method=\"post\" onsubmit=\"return confirm('Delete this record?')\">"
        "<input type=\"hidden\" name=\"csrf_token\" value=\"" + _esc(token) + "\">"
        "<input type=\"hidden\" name=\"action\" value=\"delete\"><input type=\"hidden\" name=\"uid\" value=\"" + uid + "\">"
        "<button>Delete this record</button></form>"
    )


def handle(request, session):
    from flask import redirect, send_file
    import secrets

    school = _school(session)
    if not school:
        return redirect("/school-login")
    if request.path.startswith("/portal/records/card/"):
        uid = request.path.rsplit("/", 1)[-1].strip().upper()
        row = _find(_rows(school), uid)
        path = _card_path(school, uid, (row or {}).get("photo", ""))
        if path is None:
            return "Card nahi mili", 404
        return send_file(path)
    kind = (request.view_args or {}).get("kind") or ""
    if request.path.endswith("/latest"):
        kind = "latest"
    if request.path.endswith("/all"):
        kind = "all"
    if kind in ("latest", "all"):
        try:
            cards = _ordered(school, kind == "latest")
            parts = _parts(cards)
            part = max(1, int(request.args.get("part") or 1))
            if part > len(parts):
                return "Part nahi hai", 404
            data = _pdf(parts[part - 1])
        except ValueError as exc:
            return str(exc), 404
        name = "%s-%s-part%s.pdf" % (school, kind, part)
        return send_file(data, mimetype="application/pdf", as_attachment=False, download_name=name)
    notice = error = ""
    token = session.get("records_csrf") or secrets.token_hex(16)
    session["records_csrf"] = token
    if request.method == "POST":
        import hmac
        posted = request.form.get("csrf_token", "")
        if not posted or not hmac.compare_digest(posted, token):
            error = "Page expired. Reload."
        else:
            uid = str(request.form.get("uid") or "").strip().upper()
            try:
                if request.form.get("action") == "delete":
                    _delete(school, uid)
                    notice = "Deleted " + uid
                else:
                    _save_edit(school, uid, request.form)
                    notice = "Saved " + uid
            except Exception as exc:
                error = str(exc)
        session["records_csrf"] = secrets.token_hex(16)
        token = session["records_csrf"]
    rows = _rows(school)
    lookup = str(request.args.get("id") or request.args.get("edit") or "").strip().upper()
    found = _find(rows, lookup)
    if lookup and found is None:
        error = error or ("ID nahi mili: " + lookup)
    try:
        latest_parts = _parts(_ordered(school, True))
        all_parts = _parts(_ordered(school, False))
    except ValueError:
        latest_parts = all_parts = []
    edit_uid = str(request.args.get("edit") or "").strip().upper()
    extra = ""
    for row in rows:
        if row["student_unique_id"].upper() == edit_uid:
            extra = _edit_form(school, row, token)
            break
    html = _page(school, rows, notice, error, latest_parts, all_parts, found)
    return html.replace("</main>", extra + "</main>")


def attach(app):
    if getattr(app, "_saini_school_records", False):
        return
    app._saini_school_records = True

    @app.route("/portal/records", methods=["GET", "POST"])
    def school_records_page():
        from flask import request, session
        return handle(request, session)

    @app.route("/portal/records/card/<uid>")
    def school_records_card(uid):
        from flask import request, session
        return handle(request, session)
    @app.route("/portal/records/pdf/<kind>")
    def school_records_pdf(kind):
        from flask import request, session
        return handle(request, session)
