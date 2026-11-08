from pathlib import Path
from PIL import Image
import hashlib
import json
import shutil
from datetime import datetime

root = Path(r"D:\SAINI_PHASE2_STAGING")
source_dir = Path.home() / "Downloads"
out_dir = root / "normalized_images_test"
out_dir.mkdir(parents=True, exist_ok=True)

expected = [f"LKG-MATH-Q{i:03}.png" for i in range(1, 67)]
missing = [name for name in expected if not (source_dir / name).is_file()]
if missing:
    raise SystemExit(f"STOP: Missing images: {missing}")

# Read dimensions before creating any outputs.
sizes = {}
for name in expected:
    with Image.open(source_dir / name) as im:
        sizes[name] = im.size

canvas_w = 2172
canvas_h = max(max(h for w, h in sizes.values()), 791)
print("Input image count:", len(expected))
print("Input dimensions:", sorted(set(sizes.values())))
print("Output canvas:", (canvas_w, canvas_h))

manifest = []
for name in expected:
    src = source_dir / name
    dst = out_dir / name

    with Image.open(src) as original:
        im = original.convert("RGB")
        if im.width > canvas_w or im.height > canvas_h:
            raise SystemExit(f"STOP: Image exceeds canvas: {name} {im.size}")

        # Keep original pixels at the top-left; pad only on right/bottom.
        canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
        canvas.paste(im, (0, 0))
        canvas.save(dst, "PNG", optimize=True)

    manifest.append({
        "filename": name,
        "source_size": list(sizes[name]),
        "normalized_size": [canvas_w, canvas_h],
        "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "output_sha256": hashlib.sha256(dst.read_bytes()).hexdigest()
    })

manifest_path = out_dir / "normalization_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

# Verify every output has the same dimensions.
bad = []
for name in expected:
    with Image.open(out_dir / name) as im:
        if im.size != (canvas_w, canvas_h):
            bad.append((name, im.size))

if bad:
    raise SystemExit(f"FAIL: Dimension verification failed: {bad}")

print("PASS: 66 normalized test images created.")
print("PASS: All output dimensions are identical.")
print("Manifest:", manifest_path)
print("Original Downloads images and SQLite database were not modified.")
