from pathlib import Path
p = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
lines = p.read_text(encoding="utf-8").splitlines()
for index in range(48, 100):
    if index <= len(lines):
        print("%s:%s" % (index, lines[index - 1]))
