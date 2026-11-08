from pathlib import Path
from PIL import Image, ImageDraw
import hashlib

root = Path(__file__).parent
image_dir = root / "images"
out_dir = root / "output_shortlisting_v2" / "HEADER_ALIGNMENT_AUDIT"
out_dir.mkdir(parents=True, exist_ok=True)

font_path = Path(r"C:\Windows\Fonts\BOOKOSB.TTF")
cards = []
report = []

for n in range(1, 5):
    path = image_dir / f"LKG-MATH-Q{n:03d}.png"
    if not path.is_file():
        report.append(f"Q{n}: MISSING")
        continue

    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    with Image.open(path) as im:
        im.load()
        w, h = im.size
        crop_h = min(240, h)
        crop = im.convert("RGB").crop((0, 0, w, crop_h))
        crop.thumbnail((1086, 120))

    cards.append((n, crop.copy()))
    report.append(
        f"Q{n}: dimensions={w}x{h}, "
        f"header_crop_height={crop_h}, SHA256={digest}"
    )

canvas = Image.new("RGB", (1120, max(1, len(cards)) * 165), "white")
draw = ImageDraw.Draw(canvas)

for i, (n, crop) in enumerate(cards):
    y = i * 165
    draw.text((12, y + 5), f"Q{n} HEADER", fill="blue")
    canvas.paste(crop, (12, y + 35))

output = out_dir / "Q001_Q004_HEADER_AUDIT.png"
canvas.save(output, dpi=(150, 150))

print("\n".join(report))
print("Audit image:", output)
print("Original images were not modified.")
