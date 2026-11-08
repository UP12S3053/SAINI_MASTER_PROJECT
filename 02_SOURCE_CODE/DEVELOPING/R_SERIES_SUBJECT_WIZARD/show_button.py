from pathlib import Path
p = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_data.py")
lines = p.read_text(encoding="utf-8").splitlines()
for index in range(385, 430):
    if index <= len(lines):
        print("%s:%s" % (index, lines[index - 1]))
