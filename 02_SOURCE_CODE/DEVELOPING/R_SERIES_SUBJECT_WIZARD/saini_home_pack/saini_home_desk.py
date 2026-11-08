# -*- coding: utf-8 -*-
"""New SAINI PAPER SYSTEM home. Replaces only the front page."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "saini_home.html"
LOGO = HERE / "saini-logo.png"
BUILDING = HERE / "saini-building.jpg"

ROUTES = {
    "school-master": "/school-master",
    "paper-setter": "/paper",
    "enrollment": "/admin/subjects",
    "delivery": "/saini-queue",
    "registration": "/admin/schools",
    "portal": "/school-login",
    "rates": "/saini/paper-rates",
    "documents": "/saini/archive",
    "paper-order": "/saini/order",
    "id-cards": "/saini/idcard",
}


def page():
    text = HTML.read_text(encoding="utf-8")
    text = text.replace('src="saini-logo.png"', 'src="/saini-home/logo"')
    text = text.replace('src="saini-building.jpg"', 'src="/saini-home/building"')
    text = text.replace('url("saini-building.jpg")', 'url("/saini-home/building")')
    for key, href in ROUTES.items():
        needle = 'data-module="%s" href="' % key
        at = text.find(needle)
        if at < 0:
            continue
        end = text.find('"', at + len(needle))
        text = text[:at] + needle + href + text[end:]
    return text


def attach(app):
    if "saini_home_page" in getattr(app, "view_functions", {}):
        return

    def _home():
        from flask import redirect, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/"))
        return page()

    endpoint = None
    for rule in app.url_map.iter_rules():
        if rule.rule == "/" and "GET" in (rule.methods or set()):
            endpoint = rule.endpoint
            break
    if endpoint:
        app.view_functions[endpoint] = _home
    else:
        app.route("/", methods=["GET"])(_home)

    @app.route("/saini-home/logo")
    def saini_home_logo():
        from flask import send_file
        return send_file(LOGO)

    @app.route("/saini-home/building")
    def saini_home_building():
        from flask import send_file
        return send_file(BUILDING)
