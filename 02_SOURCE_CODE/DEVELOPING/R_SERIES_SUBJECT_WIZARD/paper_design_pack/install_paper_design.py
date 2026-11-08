# -*- coding: utf-8 -*-
"""Install the approved Paper Setter design. Does not touch other modules."""
import py_compile
import shutil
from datetime import datetime
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
HERE = Path(__file__).resolve().parent
BACKUP = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX")


def main():
    if not APP.is_file():
        raise SystemExit("ABORT missing app")
    for name in ("paper_setter_desk.py", "paper_setter_design.html", "saini-logo-paper.jpg", "saini-building-paper.jpg"):
        if not (HERE / name).is_file():
            raise SystemExit("ABORT missing " + name)
    BACKUP.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(APP, BACKUP / ("subject_wizard_dev_before_paper_design_%s.py" % stamp))
    target = APP.parent
    for name in ("paper_setter_desk.py", "paper_setter_design.html", "saini-logo-paper.jpg", "saini-building-paper.jpg"):
        shutil.copy2(HERE / name, target / name)
    py_compile.compile(str(target / "paper_setter_desk.py"), doraise=True)
    print("PAPER_DESIGN_OK")
    print("page=/paper")


if __name__ == "__main__":
    main()
