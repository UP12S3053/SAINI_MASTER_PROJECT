# -*- coding: utf-8 -*-
"""Approved Paper Setter design on its own page. Original /paper is not touched."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "paper_final_design.html"


def attach(app):
    if "paper_final_design" in getattr(app, "view_functions", {}):
        return

    @app.route("/paper-design", methods=["GET"])
    def paper_final_design():
        from flask import redirect, session, url_for
        if not session.get("saini_teacher_authenticated"):
            return redirect(url_for("trial_login", next="/paper-design"))
        return HTML.read_text(encoding="utf-8")
