from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib
import sqlite3

root = Path(__file__).parent
db = root / "paper_bank.db"
source = root / "images" / "LKG-MATH-Q001.png"
font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
out_dir = root / "output_shortlisting_v2" / "LOCKED_FONT100_INTEGRATION_TEST"
output = out_dir / "LKG-MATH-Q001_FONT100.png"

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

if not source.is_file():
    raise SystemExit(f"STOP: Source missing: {source}")
if not font_path.is_file():
    raise SystemExit(f"STOP: Font missing: {font_path}")

# Read-only confirmation that selected question ID 7 points to Q001.
con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
row = con.execute(
    "SELECT id, image_path, marks FROM questions WHERE id = ?", (7,)
).fetchone()
con.close()

if row != (7, "images/LKG-MATH-Q001.png", 1.0):
    raise SystemExit(f"STOP: Unexpected question record: {row}")

source_hash_before = sha256(source)

with Image.open(source) as im:
    im.load()
    canvas = im.convert("RGB")
    width, height = canvas.size

draw = ImageDraw.Draw(canvas)
font_size = max(12, round(width * 100 / 2172))
font = ImageFont.truetype(str(font_path), font_size)

# Locked coordinates: both share the same Y coordinate.
y = round(height * 128 / 598)
qx = round(width * 170 / 2172)
mx = round(width * 1935 / 2172)

draw.text((qx, y), "Q1", font=font, fill=(0, 0, 0), anchor="mm")
draw.text((mx, y), "1 Mark", font=font, fill=(0, 0, 0), anchor="mm")

out_dir.mkdir(parents=True, exist_ok=True)
canvas.save(output, format="PNG", dpi=(300, 300))

with Image.open(output) as check:
    if check.size != (width, height):
        raise SystemExit("FAIL: Output dimensions changed.")

if sha256(source) != source_hash_before:
    raise SystemExit("FAIL: Source image changed.")

print("PASS: Selected database question ID:", row[0])
print("PASS: Font size:", font_size)
print("PASS: Shared Y coordinate:", y)
print("PASS: Output dimensions:", (width, height))
print("PASS: Source image unchanged")
print("Output:", output)
