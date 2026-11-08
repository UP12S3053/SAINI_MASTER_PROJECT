# -*- coding: utf-8 -*-
"""Approved Paper Setter design. Live questions come from the original /paper."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "paper_final_design.html"


def attach(app):
    if getattr(app, "_saini_paper_final", False):
        return
    app._saini_paper_final = True
    endpoint = None
    for rule in list(app.url_map.iter_rules()):
        if rule.rule == "/paper" and "GET" in (rule.methods or set()):
            endpoint = rule.endpoint
            break
    original = app.view_functions.get(endpoint) if endpoint else None

    @app.route("/paper-design", methods=["GET"])
    def paper_final_design():
        from flask import redirect, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/paper-design"))
        return HTML.read_text(encoding="utf-8")

    @app.route("/paper-design/bank", methods=["GET", "POST"])
    def paper_design_bank():
        from flask import redirect, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/paper-design"))
        if original is None:
            return "paper route missing", 404
        return original()
