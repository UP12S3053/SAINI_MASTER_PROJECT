from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib

root = Path(__file__).resolve().parent
source = root / "images" / "LKG-MATH-Q001.png"
outdir = root / "output_shortlisting_v2"
outdir.mkdir(parents=True, exist_ok=True)
output = outdir / "LKG-MATH-Q001_COMPOSITE_TEST.png"

if not source.is_file():
    raise SystemExit(f"STOP: Missing source image: {source}")

im = Image.open(source).convert("RGB")
draw = ImageDraw.Draw(im)

# Locate a Bookman Old Style font if installed.
candidates = [
    Path(r"C:\Windows\Fonts\BOOKOS.TTF"),
    Path(r"C:\Windows\Fonts\BOOKOSB.TTF"),
]
font_path = next((p for p in candidates if p.is_file()), None)
if font_path is None:
    raise SystemExit(
        "STOP: Bookman Old Style font not found at expected Windows paths. "
        "No output image was created."
    )

# 17 pt at 96 DPI is approximately 23 px.
font = ImageFont.truetype(str(font_path), 23)

# Provisional positions only; inspect the output before using these for all worksheets.
w, h = im.size
number_box = (int(w * 0.022), int(h * 0.08), int(w * 0.085), int(h * 0.27))
marks_box = (int(w * 0.835), int(h * 0.06), int(w * 0.965), int(h * 0.21))

def centered_text(box, text):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = x1 + ((x2 - x1) - tw) / 2 - bbox[0]
    y = y1 + ((y2 - y1) - th) / 2 - bbox[1]
    draw.text((int(x), int(y)), text, font=font, fill=(17, 17, 17))

centered_text(number_box, "Q1")
centered_text(marks_box, "1 Mark")

im.save(output, format="PNG")
print("TEST COMPOSITE CREATED")
print("Source:", source)
print("Output:", output)
print("Image size:", im.size)
print("Original SHA256:", hashlib.sha256(source.read_bytes()).hexdigest())
print("Composite SHA256:", hashlib.sha256(output.read_bytes()).hexdigest())
print("Original worksheet was not modified.")
