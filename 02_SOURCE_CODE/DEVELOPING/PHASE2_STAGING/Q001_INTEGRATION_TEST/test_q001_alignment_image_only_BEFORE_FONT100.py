from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib

root = Path(__file__).parent
source = root / "images" / "LKG-MATH-Q001.png"
out_dir = root / "output_shortlisting_v2" / "ALIGNMENT_IMAGE_ONLY_TEST"
output = out_dir / "LKG-MATH-Q001_FONT120_TEST.png"

font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")

if not source.is_file():
    raise SystemExit(f"STOP: Source image missing: {source}")
if not font_path.is_file():
    raise SystemExit(f"STOP: Bookman Bold font missing: {font_path}")

def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

source_hash_before = sha256(source)

with Image.open(source) as original:
    original.load()
    canvas = original.convert("RGB")
    width, height = canvas.size

draw = ImageDraw.Draw(canvas)
font_size = max(12, round(width * 120 / 2172))
font = ImageFont.truetype(str(font_path), font_size)

# Shared hard-coded Y coordinate, scaled from the approved 2172 x 598 layout.
y = round(height * 128 / 598)
qx = round(width * 170 / 2172)
mx = round(width * 1935 / 2172)

draw.text((qx, y), "Q1", font=font, fill=(0, 0, 0), anchor="mm")
draw.text((mx, y), "1 Mark", font=font, fill=(0, 0, 0), anchor="mm")

out_dir.mkdir(parents=True, exist_ok=True)
canvas.save(output, format="PNG", dpi=(300, 300))

with Image.open(output) as check:
    print("Output dimensions:", check.size)
    print("Source dimensions:", (width, height))
    if check.size != (width, height):
        raise SystemExit("FAIL: Output dimensions changed.")

source_hash_after = sha256(source)
if source_hash_before != source_hash_after:
    raise SystemExit("FAIL: Source image hash changed.")

print("Question font size:", font_size)
print("Marks font size:", font_size)
print("Question anchor:", (qx, y))
print("Marks anchor:", (mx, y))
print("Source SHA256 unchanged:", source_hash_before == source_hash_after)
print("PASS: Image-only test complete.")
print("Output:", output)
