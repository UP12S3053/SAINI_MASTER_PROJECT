# -*- coding: utf-8 -*-
"""Update the Paper Setter design page. Original /paper stays."""
import py_compile
import shutil
from pathlib import Path

APP = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
HERE = Path(__file__).resolve().parent


def main():
    if not APP.is_file():
        raise SystemExit("ABORT missing app")
    for name in ("paper_final_desk.py", "paper_final_design.html"):
        if not (HERE / name).is_file():
            raise SystemExit("ABORT missing " + name)
    shutil.copy2(HERE / "paper_final_desk.py", APP.parent / "paper_final_desk.py")
    shutil.copy2(HERE / "paper_final_design.html", APP.parent / "paper_final_design.html")
    py_compile.compile(str(APP.parent / "paper_final_desk.py"), doraise=True)
    print("BANK_OK")
    print("page=/paper-design")


if __name__ == "__main__":
    main()
