from pathlib import Path
from PIL import Image

src = Path.home() / "Downloads"
names = [f"LKG-MATH-Q{i:03}.png" for i in range(1, 67)]
missing = [n for n in names if not (src / n).is_file()]
sizes = {}

for name in names:
    p = src / name
    if p.is_file():
        with Image.open(p) as im:
            sizes[name] = im.size

print("EXPECTED:", len(names))
print("FOUND:", len(sizes))
print("MISSING:", missing)
print("DIMENSION GROUPS:")
groups = {}
for name, size in sizes.items():
    groups.setdefault(size, []).append(name)
for size, files in sorted(groups.items()):
    print(size, "=>", len(files), "images")

print("READY FOR BACKUP:", len(sizes) == 66 and not missing)
