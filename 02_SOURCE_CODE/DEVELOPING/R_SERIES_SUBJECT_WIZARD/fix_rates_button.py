# -*- coding: utf-8 -*-
"""Remove the extra Paper rates button that was copied with Complete paper order."""
import re
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
ANCHOR = re.compile(
    r"(?:\s*\|\s*)?<a\b[^>]*href\s*=\s*[\"']?[^\"'>\s]*paper-rates[^\"'>\s]*[\"']?[^>]*>.*?</a>(?:\s*\|\s*)?",
    re.I,
)


def fix(text):
    changed = 0
    lines = []
    for line in text.splitlines(True):
        if "/saini/order" in line and "paper-rates" in line:
            new, count = ANCHOR.subn("", line, count=1)
            if count:
                changed += 1
                line = new
        lines.append(line)
    return "".join(lines), changed


def main():
    text = APP.read_text(encoding="utf-8")
    fixed, changed = fix(text)
    if changed == 0:
        raise SystemExit("ABORT no combined Paper rates line")
    APP.write_text(fixed, encoding="utf-8")
    print("RATES_FIXED", changed)
    print("label_count", fixed.count("Paper rates (SAINI)"))


if __name__ == "__main__":
    main()
