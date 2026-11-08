from pathlib import Path
from PIL import Image

src = Path("images/LKG-MATH-Q004.png")
out = Path("output_shortlisting_v2/CENTERED_POSITION_TEST")
out.mkdir(parents=True, exist_ok=True)

im = Image.open(src)
# Inspect only the header; this does not modify the original.
crop = im.crop((0, 0, 2172, 220))
target = out / "Q004_HEADER_CROP.png"
crop.save(target)

print("Header crop:", target.resolve())
print("Crop size:", crop.size)
print("Original unchanged:", src.is_file())
