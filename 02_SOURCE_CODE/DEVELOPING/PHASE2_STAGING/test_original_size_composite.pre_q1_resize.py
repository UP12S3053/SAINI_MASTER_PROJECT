from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib

root = Path(r"D:\SAINI_PHASE2_STAGING")
source = Path.home() / "Downloads" / "LKG-MATH-Q001.png"
outdir = root / "output_shortlisting_v2"
outdir.mkdir(parents=True, exist_ok=True)
output = outdir / "LKG-MATH-Q001_ORIGINAL_SIZE_TEST.png"

if not source.is_file():
    raise SystemExit(f"STOP: Original image missing: {source}")

font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
if not font_path.is_file():
    font_path = Path(r"C:\Windows\Fonts\BOOKOS.TTF")
if not font_path.is_file():
    raise SystemExit("STOP: Bookman Old Style font file not found.")

with Image.open(source) as src:
    im = src.convert("RGB")

print("Original dimensions:", im.size)
print("Font:", font_path.name)
print("Font size: 71 px (approximately 17 pt at 300 DPI)")

draw = ImageDraw.Draw(im)
font = ImageFont.truetype(str(font_path), 71)

# PROVISIONAL PIXEL COORDINATES — verify visually before batch processing.
# Center of flower box; top-left origin (0, 0).
number_center = (132, 132)

# Center of the marks area near the upper-right strip.
marks_center = (1935, 92)

def draw_centered(text, center):
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = round(center[0] - width / 2 - bbox[0])
    y = round(center[1] - height / 2 - bbox[1])
    draw.text((x, y), text, font=font, fill=(17, 17, 17))

draw_centered("Q1", number_center)
draw_centered("1 Mark", marks_center)

im.save(output, "PNG")

print("TEST IMAGE CREATED:", output)
print("Output dimensions:", Image.open(output).size)
print("Original SHA256:", hashlib.sha256(source.read_bytes()).hexdigest())
print("Output SHA256:", hashlib.sha256(output.read_bytes()).hexdigest())
print("Original image and SQLite database were not modified.")
