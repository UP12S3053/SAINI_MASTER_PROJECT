# -*- coding: utf-8 -*-
"""Add /paper-design. Does not replace /paper."""
import py_compile
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
HERE = Path(__file__).resolve().parent
BACKUP = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")
HOOK = "\nimport paper_final_desk as _paper_final\n_paper_final.attach(app)\n"


def main():
    if not APP.is_file():
        raise SystemExit("ABORT missing app")
    for name in ("paper_final_desk.py", "paper_final_design.html"):
        if not (HERE / name).is_file():
            raise SystemExit("ABORT missing " + name)
    BACKUP.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(APP, BACKUP / ("subject_wizard_dev_before_paper_final_%s.py" % stamp))
    shutil.copy2(HERE / "paper_final_desk.py", APP.parent / "paper_final_desk.py")
    shutil.copy2(HERE / "paper_final_design.html", APP.parent / "paper_final_design.html")
    text = APP.read_text(encoding="utf-8")
    if "_paper_final.attach(app)" not in text:
        placed = False
        for marker in ('if __name__ == "__main__":', "if __name__ == '__main__':"):
            at = text.find(marker)
            if at >= 0:
                text = text[:at] + HOOK + text[at:]
                placed = True
                break
        if not placed:
            text += HOOK
        APP.write_text(text, encoding="utf-8")
        print("HOOK yes")
    else:
        print("HOOK already")
    py_compile.compile(str(APP.parent / "paper_final_desk.py"), doraise=True)
    py_compile.compile(str(APP), doraise=True)
    print("PAPER_FINAL_OK")
    print("page=/paper-design")


if __name__ == "__main__":
    main()
