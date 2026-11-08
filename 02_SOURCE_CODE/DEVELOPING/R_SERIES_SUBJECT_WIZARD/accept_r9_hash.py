from pathlib import Path
path = Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_000I_R9\deploy_r9.py")
text = path.read_text(encoding="utf-8")
old = "466E0EE1BF63698DC300A50BF07451F53889A1EE7B37A2C6E460D9551FC772F0"
new = "8E774A9754CB0A1CA0ED4099C721052FD416476770EA4BDD28C8E8FCA07BE7EF"
if text.count(old) != 1:
    raise SystemExit("HASH_LINE_NOT_FOUND")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("HASH_LINE_UPDATED")