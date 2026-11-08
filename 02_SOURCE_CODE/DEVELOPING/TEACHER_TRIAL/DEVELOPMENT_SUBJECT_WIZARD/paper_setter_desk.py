# -*- coding: utf-8 -*-
"""Approved Paper Setter design. Live form stays hidden. No script text on the page."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "paper_setter_design.html"
LOGO = HERE / "saini-logo-paper.jpg"
BUILDING = HERE / "saini-building-paper.jpg"


def _text_of(result):
    if result is None or isinstance(result, str):
        return result or ""
    get_data = getattr(result, "get_data", None)
    if not get_data:
        return ""
    try:
        return get_data(as_text=True)
    except Exception:
        return ""


def _download(result):
    if result is None or isinstance(result, str):
        return False
    headers = getattr(result, "headers", {}) or {}
    kind = (headers.get("Content-Type") or "").lower()
    disp = (headers.get("Content-Disposition") or "").lower()
    return "pdf" in kind or "spreadsheet" in kind or "excel" in kind or "octet-stream" in kind or "attachment" in disp or kind.startswith("image/")


def _redirect(result):
    return getattr(result, "status_code", 200) in (301, 302, 303, 307, 308)


def _between(html, start, end, limit=250000):
    low = html.lower()
    at = low.find(start)
    if at < 0:
        return ""
    stop = low.find(end, at)
    if stop < 0:
        return html[at:at + limit]
    return html[at:stop + len(end)]


def _strip_scripts(html):
    low = html.lower()
    out = []
    i = 0
    while True:
        at = low.find("<script", i)
        if at < 0:
            out.append(html[i:])
            break
        stop = low.find("</script>", at)
        out.append(html[i:at])
        if stop < 0:
            break
        i = stop + 9
    return "".join(out)


def _strip_photostat(html):
    low = html.lower()
    out = []
    i = 0
    while True:
        at = low.find("photostat", i)
        if at < 0:
            out.append(html[i:])
            break
        left = max(html.rfind("<", 0, at), i)
        right = html.find(">", at)
        if right < 0:
            break
        out.append(html[i:left])
        i = right + 1
    return "".join(out)


def skin(original):
    page = HTML.read_text(encoding="utf-8")
    original = original or ""
    form = _strip_photostat(_strip_scripts(_between(original, "<form", "</form>")))
    questions = _strip_photostat(_strip_scripts(_between(original, "<body", "</body>")))
    if not questions:
        questions = _strip_scripts(original)
    if form and form in questions:
        questions = questions.replace(form, "", 1)
    if not form:
        form = "<p>Live form will load with the paper setter.</p>"
    if not questions.strip():
        questions = "<p>Choose class and subject, then press सवाल दिखाओ.</p>"
    page = page.replace("LIVE_FORM", form)
    page = page.replace("LIVE_QUESTIONS", questions)
    return page


def attach(app):
    if getattr(app, "_saini_paper_skin", False):
        return
    app._saini_paper_skin = True
    endpoint = None
    for rule in list(app.url_map.iter_rules()):
        if rule.rule == "/paper" and "GET" in (rule.methods or set()):
            endpoint = rule.endpoint
            break
    original = app.view_functions.get(endpoint) if endpoint else None

    def _paper(*args, **kwargs):
        from flask import redirect, request, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/paper"))
        if original is None:
            return skin("")
        if request.method != "GET" or request.args.get("raw") == "1":
            return original(*args, **kwargs)
        try:
            result = original(*args, **kwargs)
        except Exception:
            return original(*args, **kwargs)
        if _download(result) or _redirect(result):
            return result
        try:
            return skin(_text_of(result))
        except Exception:
            return result

    if endpoint:
        app.view_functions[endpoint] = _paper
    else:
        app.route("/paper", methods=["GET", "POST"])(_paper)

    if "paper_ui_logo" not in app.view_functions:
        @app.route("/paper-ui/logo")
        def paper_ui_logo():
            from flask import send_file
            return send_file(LOGO)

        @app.route("/paper-ui/building")
        def paper_ui_building():
            from flask import send_file
            return send_file(BUILDING)
