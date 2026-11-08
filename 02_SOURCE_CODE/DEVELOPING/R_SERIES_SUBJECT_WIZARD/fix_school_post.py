# -*- coding: utf-8 -*-
"""Allow Save to Excel to POST to /school."""
from pathlib import Path

DESK = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_master_desk.py")
OLD = '''    if endpoint:
        app.view_functions[endpoint] = _school
    else:
        app.route("/school", methods=["GET", "POST"])(_school)
'''
NEW = '''    for rule in app.url_map.iter_rules():
        if rule.rule == "/school" and rule.methods is not None:
            rule.methods.add("GET")
            rule.methods.add("POST")
    if endpoint:
        app.view_functions[endpoint] = _school
    else:
        app.route("/school", methods=["GET", "POST"])(_school)
'''


def main():
    text = DESK.read_text(encoding="utf-8")
    if "rule.methods.add(\"POST\")" in text:
        print("ALREADY")
        return
    if OLD not in text:
        raise SystemExit("ABORT school block missing")
    DESK.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("SCHOOL_POST_OK")


if __name__ == "__main__":
    main()
