# -*- coding: utf-8 -*-
"""Add school-only records and class-wise ID card PDFs to the teacher portal."""
import py_compile
import shutil
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
PORTAL = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_portal.py")
HERE = Path(__file__).resolve().parent
HOOK = "\nimport school_records as _school_records\n_school_records.attach(app)\n"
LINK = '<p><a href="/portal/records">School records and ID card PDFs</a></p>\n'


def attach_source():
    return '''
def attach(app):
    if getattr(app, "_saini_school_records", False):
        return
    app._saini_school_records = True

    @app.route("/portal/records", methods=["GET", "POST"])
    def school_records_page():
        from flask import request, session
        return handle(request, session)

    @app.route("/portal/records/pdf/<kind>")
    def school_records_pdf(kind):
        from flask import request, session
        return handle(request, session)
'''


def allow_portal(text):
    if 'request.path.startswith("/portal/records")' in text:
        print("GUARD already")
        return text
    needle = "if request.path in ("
    at = text.find(needle)
    if at < 0:
        print("GUARD missing")
        return text
    end = text.find("):", at)
    if end < 0:
        print("GUARD missing")
        return text
    print("GUARD yes")
    return text[:end] + ' or request.path.startswith("/portal/records")' + text[end:]


def main():
    module = HERE / "school_records.py"
    text = module.read_text(encoding="utf-8")
    if "def attach(" not in text:
        module.write_text(text.rstrip() + "\n" + attach_source(), encoding="utf-8")
    py_compile.compile(str(module), doraise=True)
    shutil.copy2(module, APP.parent / "school_records.py")
    app = APP.read_text(encoding="utf-8")
    if "_school_records.attach(app)" not in app:
        marker = 'if __name__ == "__main__":'
        if marker not in app:
            raise SystemExit("ABORT main missing")
        app = app.replace(marker, HOOK + marker, 1)
        print("HOOK yes")
    else:
        print("HOOK already")
    app = allow_portal(app)
    APP.write_text(app, encoding="utf-8")
    portal = PORTAL.read_text(encoding="utf-8")
    if "/portal/records" not in portal:
        needle = '<form method="post" action="/school-logout">'
        if needle not in portal:
            raise SystemExit("ABORT portal link point missing")
        PORTAL.write_text(portal.replace(needle, LINK + needle, 1), encoding="utf-8")
        print("PORTAL_LINK yes")
    else:
        print("PORTAL_LINK already")
    py_compile.compile(str(APP), doraise=True)
    print("RECORDS_OK")
    print("page=/portal/records")


if __name__ == "__main__":
    main()
