from pathlib import Path
p = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\app_phase2_shortlisting_v2_trial_secure_subject_wizard_dev.py")
lines = p.read_text(encoding="utf-8").splitlines()
for start, end in ((228, 260), (360, 420), (1238, 1270)):
    print("---%s-%s---" % (start, end))
    for index in range(start, end + 1):
        if index <= len(lines):
            print("%s:%s" % (index, lines[index - 1]))
root = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\production_jobs")
print("JOBS", root.is_dir())
if root.is_dir():
    names = sorted(root.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)[:8]
    for item in names:
        print(item.name)
