# -*- coding: utf-8 -*-
"""Put the new home design on the development paper system. Run once."""
import hashlib
import py_compile
import re
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
HERE = Path(__file__).resolve().parent
BACKUP = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
HOOK = "\nimport saini_home_desk as _saini_home\n_saini_home.attach(app)\n"
LABELS = {
    "School Master": "school-master",
    "Paper Setter": "paper-setter",
    "Subject Enrollment": "enrollment",
    "delivery queue": "delivery",
    "School Registration": "registration",
    "School Portal": "portal",
    "Paper rates": "rates",
    "Saved documents": "documents",
    "Complete paper order": "paper-order",
    "ID Cards": "id-cards",
}


def href_near(text, label):
    at = text.find(label)
    if at < 0:
        return ""
    window = text[max(0, at - 220):at + 80]
    found = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', window)
    return found[-1] if found else ""


def apply_live_routes(desk_text, app_text):
    for label, key in LABELS.items():
        href = href_near(app_text, label)
        if not href or href.startswith("#"):
            continue
        desk_text = desk_text.replace(
            '"%s": "%s"' % (key, {
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
            }[key]),
            '"%s": "%s"' % (key, href),
            1,
        )
        print("ROUTE", key, href)
    return desk_text


def main():
    if not APP.is_file():
        raise SystemExit("ABORT missing " + str(APP))
    for name in ("saini_home.html", "saini_home_desk.py", "saini-logo.png", "saini-building.jpg"):
        if not (HERE / name).is_file():
            raise SystemExit("ABORT missing " + name)
    BACKUP.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(APP, BACKUP / ("subject_wizard_dev_before_home_%s.py" % stamp))
    app_text = APP.read_text(encoding="utf-8")
    desk = (HERE / "saini_home_desk.py").read_text(encoding="utf-8")
    desk = apply_live_routes(desk, app_text)
    target = APP.parent / "saini_home_desk.py"
    target.write_text(desk, encoding="utf-8")
    shutil.copy2(HERE / "saini_home.html", APP.parent / "saini_home.html")
    shutil.copy2(HERE / "saini-logo.png", APP.parent / "saini-logo.png")
    shutil.copy2(HERE / "saini-building.jpg", APP.parent / "saini-building.jpg")
    if "_saini_home.attach(app)" not in app_text:
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
    print("HOME_OK")
    print("page=/")


if __name__ == "__main__":
    main()
