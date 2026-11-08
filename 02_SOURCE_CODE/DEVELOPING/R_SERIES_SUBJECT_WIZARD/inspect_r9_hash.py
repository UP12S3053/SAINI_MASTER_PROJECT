from datetime import datetime
from pathlib import Path
import hashlib
from openpyxl import load_workbook

root = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels")
expected = {
    "SAINI_ID_CARD.py": "08F68584254CE7E016BCB075EE25F59EEB94803550F82D8FF4BFF844453CB0E1",
    "school_config_front.xlsx": "466E0EE1BF63698DC300A50BF07451F53889A1EE7B37A2C6E460D9551FC772F0",
    "ID_CARD_PROJECT/templates/IDCARD/BSM.png": "FE644757E1F23AAAB47C46AE2880F8DFD4CCDE63B645C50B6C10B7C855151B73",
}
for rel, old in expected.items():
    path = root / rel
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    stamp = datetime.fromtimestamp(path.stat().st_mtime)
    print(("MATCH" if digest == old else "DIFF"), rel, digest, path.stat().st_size, stamp)

book = load_workbook(root / "school_config_front.xlsx", read_only=True, data_only=True)
sheet = book["Sheet1"]
rows = list(sheet.iter_rows(values_only=True))
book.close()
header = list(rows[0])
code_at = header.index("school_code")
name_at = header.index("SCHOOLNAME")
template_at = header.index("template")
card_at = header.index("CARD")
type_at = header.index("CARD_TYPE")
print("ROWS", len(rows))
for number, row in enumerate(rows, start=1):
    if str(row[code_at] or "").strip().upper() == "BSM":
        print("BSM", number, repr(row[name_at]), repr(row[template_at]), repr(row[card_at]), repr(row[type_at]))
clean = root / "ID_CARD_PROJECT" / "templates" / "IDCARD" / "BSM_PUBLIC_SCHOOL_CLEAN.png"
print("CLEAN_EXISTS", clean.exists())
print("READ_ONLY_DONE")