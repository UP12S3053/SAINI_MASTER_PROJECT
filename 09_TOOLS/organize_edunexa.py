"""
EDUNEXA File Organizer
======================
सही स्पेलिंग: EDUNEXA

यह स्क्रिप्ट आपके मौजूदा प्रोजेक्ट से फाइलें उठाकर
EDUNEXA ऑफिशियल स्ट्रक्चर में सही जगह डालती है।

CORE      = स्थिर, टेस्टेड कोड
DEVELOPING = नया काम / प्रयोग

उपयोग:
1. इस स्क्रिप्ट को अपने मुख्य प्रोजेक्ट फोल्डर में रखें।
2. python organize_edunexa.py चलाएं।
"""

import os
import shutil
from pathlib import Path

# ============ CONFIG ============
MOVE = False  # True करने पर मूव होगा, False = कॉपी (सुरक्षित)

SOURCE_DIR = Path(".").resolve()
TARGET_ROOT = SOURCE_DIR / "EDUNEXA"

# फाइल मैपिंग
FILE_MAP = {
    # Python core files → CORE
    "SAINI_ID_CARD.py": "02_SOURCE_CODE/CORE/id_card",
    "saini_id_card.py": "02_SOURCE_CODE/CORE/id_card",
    "EXAM_ASSISTANT.py": "02_SOURCE_CODE/CORE/exam_paper",
    "exam_assistant.py": "02_SOURCE_CODE/CORE/exam_paper",
    "PAPER.py": "02_SOURCE_CODE/CORE/exam_paper",
    "paper.py": "02_SOURCE_CODE/CORE/exam_paper",
    "MAIN_ASSISTANT.py": "02_SOURCE_CODE/CORE/main_assistant",
    "main_assistant.py": "02_SOURCE_CODE/CORE/main_assistant",

    # Database
    "*.db": "03_DATABASE",
    "*.sqlite": "03_DATABASE",
    "*.sqlite3": "03_DATABASE",

    # Media
    "*.jpg": "06_MEDIA",
    "*.jpeg": "06_MEDIA",
    "*.png": "06_MEDIA",
    "*.gif": "06_MEDIA",
    "*.webp": "06_MEDIA",
    "*.pdf": "06_MEDIA",
    "*.ttf": "06_MEDIA",
    "*.otf": "06_MEDIA",

    # Data
    "*.xlsx": "03_DATABASE",
    "*.xls": "03_DATABASE",
    "*.csv": "03_DATABASE",
    "*.json": "03_DATABASE",
}

FOLDER_MAP = {
    "photos": "06_MEDIA",
    "images": "06_MEDIA",
    "pdfs": "06_MEDIA",
    "fonts": "06_MEDIA",
}


def ensure_dirs():
    dirs = [
        "01_DOCUMENTATION",
        "02_SOURCE_CODE/CORE/id_card",
        "02_SOURCE_CODE/CORE/exam_paper",
        "02_SOURCE_CODE/CORE/main_assistant",
        "02_SOURCE_CODE/DEVELOPING",
        "03_DATABASE",
        "04_AI_MODELS",
        "05_DESIGNS",
        "06_MEDIA",
        "07_DEPLOYMENT",
        "08_TESTING",
        "09_TOOLS",
        "10_BACKUP",
    ]
    for d in dirs:
        (TARGET_ROOT / d).mkdir(parents=True, exist_ok=True)
    print(f"✓ EDUNEXA स्ट्रक्चर तैयार: {TARGET_ROOT}")


def match_destination(filename: str) -> str | None:
    name_lower = filename.lower()
    for pattern, dest in FILE_MAP.items():
        if pattern.startswith("*."):
            if name_lower.endswith(pattern[1:]):
                return dest
        elif name_lower == pattern.lower():
            return dest
    return None


def organize():
    ensure_dirs()
    copied = moved = skipped = 0

    print(f"\nस्रोत: {SOURCE_DIR}")
    print(f"लक्ष्य: {TARGET_ROOT}")
    print(f"मोड: {'MOVE' if MOVE else 'COPY'}\n")

    for item in SOURCE_DIR.iterdir():
        if item.name.startswith(".") or item.name.upper() == "EDUNEXA":
            continue

        if item.is_file():
            dest_rel = match_destination(item.name)
            if dest_rel:
                dest_path = TARGET_ROOT / dest_rel / item.name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                if MOVE:
                    shutil.move(str(item), str(dest_path))
                    print(f"  → MOVED: {item.name} → {dest_rel}/")
                    moved += 1
                else:
                    shutil.copy2(str(item), str(dest_path))
                    print(f"  → COPIED: {item.name} → {dest_rel}/")
                    copied += 1
            else:
                skipped += 1

        elif item.is_dir():
            folder_dest = FOLDER_MAP.get(item.name.lower())
            if folder_dest:
                dest_path = TARGET_ROOT / folder_dest / item.name
                if MOVE:
                    shutil.move(str(item), str(dest_path))
                    print(f"  → MOVED FOLDER: {item.name} → {folder_dest}/")
                    moved += 1
                else:
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(str(item), str(dest_path))
                    print(f"  → COPIED FOLDER: {item.name} → {folder_dest}/")
                    copied += 1

    print("\n" + "="*50)
    print("हो गया!")
    print(f"  Copied: {copied}")
    print(f"  Moved:  {moved}")
    print(f"  Skipped: {skipped}")
    print("\nCORE = स्थिर कोड")
    print("DEVELOPING = नया काम / टेस्टिंग")
    print("सक्सेस होने पर DEVELOPING से CORE में मर्ज करें।")


if __name__ == "__main__":
    organize()
