from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib

src = Path.home() / "Downloads" / "LKG-MATH-Q001.png"
out = Path(r"D:\SAINI_PHASE2_STAGING\output_shortlisting_v2\LKG-MATH-Q001_FINAL_TEST.png")
out.parent.mkdir(parents=True, exist_ok=True)

font_candidates = [
    Path(r"C:\Windows\Fonts\BOOKOSB.TTF"),
    Path(r"C:\Windows\Fonts\BOOKOS.TTF"),
]
font_path = next((p for p in font_candidates if p.is_file()), None)

if not src.is_file():
    raise SystemExit(f"STOP: Source image missing: {src}")
if font_path is None:
    raise SystemExit("STOP: Bookman Old Style font not found.")

with Image.open(src) as original:
    im = original.convert("RGB")
    original_size = im.size
    original_hash = hashlib.sha256(src.read_bytes()).hexdigest()

draw = ImageDraw.Draw(im)

# Question number: same X; Y moved down by 20 px.
question_font = ImageFont.truetype(str(font_path), 90)
marks_font = ImageFont.truetype(str(font_path), 71)

def centered(text, center, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = round(center[0] - tw / 2 - bbox[0])
    y = round(center[1] - th / 2 - bbox[1])
    draw.text((x, y), text, font=font, fill=(17, 17, 17))

# Provisional coordinates from the previous visual test.
centered("Q1", (132, 120), question_font)
centered("1 Mark", (1935, 92), marks_font)

if im.size != original_size:
    raise SystemExit("STOP: Output dimensions unexpectedly changed.")

im.save(out, "PNG")

print("PASS: Test composite saved:", out)
print("Original dimensions:", original_size)
print("Output dimensions:", Image.open(out).size)
print("Original SHA256:", original_hash)
print("Original file remains unchanged.")












