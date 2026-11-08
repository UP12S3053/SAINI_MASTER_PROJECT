# -*- coding: utf-8 -*-
"""School Master skin. Same /school save and validate, new page only."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "school_master.html"
LOGO = HERE / "saini-logo-master.jpg"
BUILDING = HERE / "saini-building-master.jpg"

FIELDS = {
    "code": "school_code",
    "name": "school_name",
    "mobile": "mobile",
    "principal": "principal",
    "address": "address",
}
BUTTONS = {"validate": "validate", "save": "save"}
MASTER = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\SCHOOL_MASTER.xlsx")
COLUMNS = ["SCHOOL_CODE", "SCHOOL_NAME", "SHEET_ID", "ACTIVE", "MOBILE", "PRINCIPAL", "ADDRESS"]


def _esc(value):
    import html as html_lib
    return html_lib.escape("" if value is None else str(value), quote=True)


def page(values=None, status="", bad=False):
    values = values or {}
    text = HTML.read_text(encoding="utf-8")
    text = text.replace('src="saini-logo.jpg"', 'src="/school-ui/logo"')
    text = text.replace('url("saini-building.jpg")', 'url("/school-ui/building")')
    for key, name in FIELDS.items():
        text = text.replace('data-field="%s" name="' % key, 'data-field="%s" name="%s" data-keep="' % (key, name), 1)
        text = text.replace("{{%s}}" % key, _esc(values.get(name, values.get(key, ""))))
    for key, name in BUTTONS.items():
        text = text.replace('data-button="%s" name="' % key, 'data-button="%s" name="%s" data-keep="' % (key, name), 1)
    text = text.replace("{{status}}", _esc(status))
    text = text.replace("{{status_class}}", "bad" if bad else "")
    return text


def _text_of(result):
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    get_data = getattr(result, "get_data", None)
    if get_data:
        try:
            return get_data(as_text=True)
        except Exception:
            return ""
    return ""


def _download(result):
    if result is None or isinstance(result, str):
        return False
    headers = getattr(result, "headers", {}) or {}
    kind = (headers.get("Content-Type") or "").lower()
    disp = (headers.get("Content-Disposition") or "").lower()
    return "spreadsheet" in kind or "excel" in kind or "octet-stream" in kind or "attachment" in disp


def _values_from(html):
    found = {}
    for key, name in FIELDS.items():
        match = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), html or "")
        if not match:
            match = re.search(r'value="([^"]*)"[^>]*name="%s"' % re.escape(name), html or "")
        if match:
            found[name] = match.group(1)
        area = re.search(r'<textarea[^>]*name="%s"[^>]*>(.*?)</textarea>' % re.escape(name), html or "", re.S)
        if area:
            found[name] = area.group(1)
    return found


def _status_from(html):
    for pattern in (r'class="[^"]*(?:msg|status|flash|ok|error)[^"]*"[^>]*>(.*?)<', r"<p[^>]*>(Saved.*?)<", r"<p[^>]*>(.*?Excel.*?)<"):
        match = re.search(pattern, html or "", re.I | re.S)
        if match:
            text = re.sub(r"<[^>]+>", "", match.group(1))
            text = " ".join(text.split())
            if text:
                return text
    return ""


def _book():
    import openpyxl
    if MASTER.is_file():
        book = openpyxl.load_workbook(MASTER)
        sheet = book.active
    else:
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.append(COLUMNS)
    header = [str(cell.value or "").strip().upper() for cell in sheet[1]]
    for name in COLUMNS:
        if name not in header:
            sheet.cell(1, len(header) + 1).value = name
            header.append(name)
    return book, sheet, {name: header.index(name) + 1 for name in header if name}


def _lookup(code):
    book, sheet, cols = _book()
    code = str(code or "").strip().upper()
    for row in range(2, sheet.max_row + 1):
        if str(sheet.cell(row, cols["SCHOOL_CODE"]).value or "").strip().upper() == code:
            found = {
                "school_code": code,
                "school_name": str(sheet.cell(row, cols.get("SCHOOL_NAME", 2)).value or ""),
                "mobile": str(sheet.cell(row, cols["MOBILE"]).value or "") if "MOBILE" in cols else "",
                "principal": str(sheet.cell(row, cols["PRINCIPAL"]).value or "") if "PRINCIPAL" in cols else "",
                "address": str(sheet.cell(row, cols["ADDRESS"]).value or "") if "ADDRESS" in cols else "",
            }
            book.close()
            return found
    book.close()
    return None


def _save(form):
    code = str(form.get("school_code") or "").strip().upper()
    name = str(form.get("school_name") or "").strip()
    if not code or not name:
        raise ValueError("School code and school name are required")
    book, sheet, cols = _book()
    target = None
    for row in range(2, sheet.max_row + 1):
        if str(sheet.cell(row, cols["SCHOOL_CODE"]).value or "").strip().upper() == code:
            target = row
            break
    if target is None:
        target = sheet.max_row + 1
        if str(sheet.cell(target, cols["SCHOOL_CODE"]).value or "").strip():
            target += 1
    values = {
        "SCHOOL_CODE": code,
        "SCHOOL_NAME": name,
        "ACTIVE": "YES",
        "MOBILE": str(form.get("mobile") or "").strip(),
        "PRINCIPAL": str(form.get("principal") or "").strip(),
        "ADDRESS": str(form.get("address") or "").strip(),
    }
    for key, value in values.items():
        if key in cols:
            sheet.cell(target, cols[key]).value = value
    if "SHEET_ID" in cols and not sheet.cell(target, cols["SHEET_ID"]).value:
        sheet.cell(target, cols["SHEET_ID"]).value = ""
    book.save(MASTER)
    book.close()
    return code


def attach(app):
    if getattr(app, "_saini_school_master", False):
        return
    app._saini_school_master = True
    endpoint = None
    for rule in app.url_map.iter_rules():
        if rule.rule == "/school" and rule.methods is not None:
            rule.methods.add("GET")
            rule.methods.add("POST")
            endpoint = rule.endpoint
            break
    original = app.view_functions.get(endpoint) if endpoint else None

    def _school(*args, **kwargs):
        from flask import redirect, request, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/school"))
        if original is None:
            return page()
        if request.method == "GET":
            return page()
        code = str(request.form.get("school_code") or "").strip().upper()
        try:
            if request.form.get(BUTTONS["save"]):
                saved = _save(request.form)
                values = _lookup(saved) or dict(request.form)
                return page(values, "Saved " + saved + " to SCHOOL_MASTER.xlsx")
            found = _lookup(code)
            if found:
                return page(found, "Found " + found["school_name"])
            return page({"school_code": code}, "School code not found. Fill details and Save.", True)
        except Exception as exc:
            return page(dict(request.form), str(exc), True)

    if endpoint:
        app.view_functions[endpoint] = _school
    else:
        app.route("/school", methods=["GET", "POST"])(_school)

    @app.route("/school-ui/logo")
    def school_ui_logo():
        from flask import send_file
        return send_file(LOGO)

    @app.route("/school-ui/building")
    def school_ui_building():
        from flask import send_file
        return send_file(BUILDING)
