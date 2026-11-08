# -*- coding: utf-8 -*-
"""Put the new School Master design on /school. Run once."""
import py_compile
import re
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
HERE = Path(__file__).resolve().parent
BACKUP = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
HOOK = "\nimport school_master_desk as _school_master\n_school_master.attach(app)\n"
LABELS = (
    ("code", ("School Code", "school code")),
    ("name", ("School Name", "school name")),
    ("mobile", ("Mobile", "mobile")),
    ("principal", ("Principal", "principal")),
    ("address", ("School Address", "Address", "address")),
)


def name_before(text, label):
    at = text.lower().find(label.lower())
    if at < 0:
        return ""
    window = text[max(0, at - 400):at + 120]
    found = re.findall(r'name\s*=\s*["\']([^"\']+)["\']', window)
    return found[-1] if found else ""


def apply_fields(desk, app_text):
    for key, labels in LABELS:
        found = ""
        for label in labels:
            found = name_before(app_text, label)
            if found:
                break
        if not found:
            continue
        desk = desk.replace('"%s": "%s"' % (key, {
            "code": "school_code",
            "name": "school_name",
            "mobile": "mobile",
            "principal": "principal",
            "address": "address",
        }[key]), '"%s": "%s"' % (key, found), 1)
        print("FIELD", key, found)
    for key, words in (("validate", ("Validate", "validate")), ("save", ("Save to Excel", "save"))):
        at = -1
        for word in words:
            at = app_text.find(word)
            if at >= 0:
                break
        if at < 0:
            continue
        window = app_text[max(0, at - 180):at + 40]
        found = re.findall(r'name\s*=\s*["\']([^"\']+)["\']', window)
        if not found:
            continue
        old = "validate" if key == "validate" else "save"
        desk = desk.replace('"%s": "%s"' % (key, old), '"%s": "%s"' % (key, found[-1]), 1)
        print("BUTTON", key, found[-1])
    return desk


def main():
    if not APP.is_file():
        raise SystemExit("ABORT missing app")
    for name in ("school_master.html", "school_master_desk.py", "saini-logo-master.jpg", "saini-building-master.jpg"):
        if not (HERE / name).is_file():
            raise SystemExit("ABORT missing " + name)
    BACKUP.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(APP, BACKUP / ("subject_wizard_dev_before_school_%s.py" % stamp))
    app_text = APP.read_text(encoding="utf-8")
    desk = apply_fields((HERE / "school_master_desk.py").read_text(encoding="utf-8"), app_text)
    target = APP.parent / "school_master_desk.py"
    target.write_text(desk, encoding="utf-8")
    for name in ("school_master.html", "saini-logo-master.jpg", "saini-building-master.jpg"):
        shutil.copy2(HERE / name, APP.parent / name)
    if "_school_master.attach(app)" not in app_text:
        placed = False
        for marker in ('if __name__ == "__main__":', "if __name__ == '__main__':"):
            at = app_text.find(marker)
            if at >= 0:
                app_text = app_text[:at] + HOOK + app_text[at:]
                placed = True
                break
        if not placed:
            app_text += HOOK
        APP.write_text(app_text, encoding="utf-8")
        print("HOOK yes")
    else:
        print("HOOK already")
    py_compile.compile(str(target), doraise=True)
    py_compile.compile(str(APP), doraise=True)
    print("SCHOOL_OK")
    print("page=/school")


if __name__ == "__main__":
    main()
