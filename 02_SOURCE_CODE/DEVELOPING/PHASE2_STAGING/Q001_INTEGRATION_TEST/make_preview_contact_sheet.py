from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import hashlib

root = Path("output_shortlisting_v2/DYNAMIC_PREVIEW_TEST")
files = sorted(root.glob("ORDER_*_*.png"))

if len(files) != 4:
    raise SystemExit(f"STOP: Expected 4 images; found {len(files)}")

thumbs = []
for p in files:
    im = Image.open(p).convert("RGB")
    im.thumbnail((1000, 350))
    tile = Image.new("RGB", (1040, 400), "white")
    tile.paste(im, (20, 35))
    ImageDraw.Draw(tile).text((20, 10), p.name, fill="black")
    thumbs.append(tile)

sheet = Image.new("RGB", (1040, 1600), "#dddddd")
for i, tile in enumerate(thumbs):
    sheet.paste(tile, (0, i * 400))

out = root / "DYNAMIC_PREVIEW_CONTACT_SHEET.jpg"
sheet.save(out, quality=95)
print("Contact sheet:", out.resolve())
print("Original images were not modified.")
