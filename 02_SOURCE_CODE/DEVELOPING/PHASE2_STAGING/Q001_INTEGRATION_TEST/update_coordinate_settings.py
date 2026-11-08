from pathlib import Path
import re

p = Path("coordinate_tester.py")
code = p.read_text(encoding="utf-8-sig")

updates = {
    "FONT_SIZE": 100,
    "Q_X": 150,
    "Q_Y": 110,
    "MARKS_X": 2090,
    "MARKS_Y": 85,
}

for name, value in updates.items():
    pattern = rf"(?m)^{name}\s*=\s*-?\d+\s*(?:#.*)?$"
    code, count = re.subn(pattern, f"{name} = {value}", code)
    if count != 1:
        raise SystemExit(
            f"STOP: {name} ki ek setting nahi mili; file update nahi ki."
        )

p.write_text(code, encoding="utf-8")

print("Updated settings:")
for name in updates:
    match = re.search(rf"(?m)^{name}\s*=\s*.*$", code)
    print(match.group(0))

print("Anchor settings unchanged.")
print("Original images and database untouched.")
