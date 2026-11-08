import pathlib
files = [
    r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_data.py",
    r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_delivery.py",
]
keys = (
    "action ==",
    "Unknown",
    "part not in",
    "Shipping",
    "shipping_block",
    "save_order",
    "combine",
    "Schools only request",
    "take_line",
    "Production line",
)
for path in files:
    print("FILE", path)
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines) if any(k in line for k in keys)]
    shown = set()
    for i in hits:
        start = max(0, i - 2)
        end = min(len(lines), i + 3)
        for n in range(start, end):
            if n not in shown:
                print("%s:%s" % (n + 1, lines[n]))
                shown.add(n)
        print("---")
