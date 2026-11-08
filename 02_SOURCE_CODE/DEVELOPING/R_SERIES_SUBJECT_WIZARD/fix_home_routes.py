# -*- coding: utf-8 -*-
"""Fix homepage routes. Known modules stay on their real paths."""
import re
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
DESK = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\saini_home_desk.py")

KNOWN = {
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


def school_master(text):
    at = text.find("School Master")
    if at < 0:
        return "/school-master"
    window = text[max(0, at - 500):at]
    found = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', window)
    if not found:
        return "/school-master"
    href = found[-1]
    if href in KNOWN.values():
        return "/school-master"
    return href


def main():
    app = APP.read_text(encoding="utf-8")
    desk = DESK.read_text(encoding="utf-8")
    routes = {"school-master": school_master(app)}
    routes.update(KNOWN)
    block = "ROUTES = {\n" + "".join('    "%s": "%s",\n' % (k, v) for k, v in routes.items()) + "}\n"
    new, n = re.subn(r"ROUTES = \{.*?\}\n", block, desk, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("ABORT routes block missing")
    DESK.write_text(new, encoding="utf-8")
    for key, href in routes.items():
        print("ROUTE", key, href)
    print("ROUTES_FIXED")


if __name__ == "__main__":
    main()
