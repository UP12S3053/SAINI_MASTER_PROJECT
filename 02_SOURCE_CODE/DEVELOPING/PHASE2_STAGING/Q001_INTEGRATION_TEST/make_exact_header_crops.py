from pathlib import Path
from PIL import Image

root = Path("images")
out = Path("output_shortlisting_v2/HEADER_ALIGNMENT_AUDIT/EXACT_CROPS")
out.mkdir(parents=True, exist_ok=True)

for n in range(1, 5):
    src = root / f"LKG-MATH-Q{n:03d}.png"
    if not src.exists():
        print("MISSING:", src)
        continue

    with Image.open(src) as im:
        w, h = im.size
        crop = im.crop((0, 0, w, min(180, h)))
        dest = out / f"Q{n}_HEADER_TOP180.png"
        crop.save(dest, dpi=(300, 300))
        print(f"Q{n}: source={w}x{h}, crop={crop.size}, saved={dest}")
