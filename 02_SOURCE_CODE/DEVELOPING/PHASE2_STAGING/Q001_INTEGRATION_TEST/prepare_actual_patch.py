from pathlib import Path
import re
import py_compile

path = Path("app_phase2_shortlisting_v2.py")
backup = Path("app_phase2_shortlisting_v2.py.before_actual_flow_patch")

if not backup.is_file():
    raise SystemExit("STOP: Backup not found.")

source = path.read_text(encoding="utf-8")
pattern = r"function generatePaper\(\) \{.*?\n\}"
match = re.search(pattern, source, re.S)

if not match:
    raise SystemExit("STOP: generatePaper() not found.")

if "fetch('/actual/'" in match.group():
    raise SystemExit("STOP: Actual route call already exists.")

print("Pre-check passed. No changes made.")
print("Next: prepare the replacement and validate it before applying.")
