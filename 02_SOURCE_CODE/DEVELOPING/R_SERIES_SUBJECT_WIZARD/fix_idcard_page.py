from pathlib import Path
p = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\idcard_desk.py")
t = p.read_text(encoding="utf-8")
old = "    return percent, label\n    options = "
new = "    return percent, label\n\n\ndef _page(token, notice, job_id=\"\"):\n    options = "
if "def _page(" not in t:
    if old not in t:
        raise SystemExit("ABORT pattern missing")
    t = t.replace(old, new, 1)
    print("PAGE_RESTORED")
else:
    print("PAGE_ALREADY")
t2 = t.replace(".bar div{height:100%;background", ".bar div{height:100%%;background", 1)
if t2 != t:
    print("CSS_FIXED")
    t = t2
p.write_text(t, encoding="utf-8")
compile(t, str(p), "exec")
print("IDCARD_OK")
