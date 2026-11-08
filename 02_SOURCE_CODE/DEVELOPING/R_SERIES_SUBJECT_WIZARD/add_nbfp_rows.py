# -*- coding: utf-8 -*-
"""Append the 10 enrolled NBFP students into student_data.xlsx."""
from pathlib import Path
import pandas as pd

MASTER = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\student_data.xlsx")
CSV = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\CSV\NBFP.csv")
PHOTOS = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\PHOTO_LIBRARY\NBFP")

UIDS = {
    "SARIK": "NBFP6004",
    "SAHIL": "NBFP4002",
    "AMAN": "NBFP6005",
    "AKSHA": "NBFP1009",
    "SUMAIYA": "NBFP1010",
    "ABDUL AHMAD": "NBFP30005",
    "ABBUZAR": "NBFP30006",
    "SHAN MOHD": "NBFP50002",
    "MAYRA": "NBFP1011",
    "JOYA": "NBFP20003",
}


def key(name):
    return " ".join(str(name or "").upper().split())


def main():
    if not MASTER.is_file():
        raise SystemExit("ABORT excel missing")
    try:
        book = pd.read_excel(MASTER, dtype=str)
    except PermissionError:
        raise SystemExit("ABORT excel open. Band karke dubara chalao.")
    csv = pd.read_csv(CSV, dtype=str) if CSV.is_file() else pd.DataFrame()
    by_name = {key(row.get("student_name")): row for _, row in csv.iterrows()}
    have = set(str(v).strip().upper() for v in book.get("student_unique_id", []))
    rows = []
    for name, uid in UIDS.items():
        if uid in have:
            print("HAVE", uid)
            continue
        src = by_name.get(name, {})
        photo = PHOTOS / (uid + ".jpg")
        rows.append({
            "student_name": str(src.get("student_name") or name).strip(),
            "class": str(src.get("class") or "").strip(),
            "school_code": "NBFP",
            "mob_number": str(src.get("mob_number") or "").strip(),
            "address": str(src.get("address") or "").strip(),
            "father_name": str(src.get("father_name") or "").strip(),
            "student_unique_id": uid,
            "STUDENT_PHOTO_PATH": str(photo) if photo.is_file() else "",
        })
    if not rows:
        print("NOTHING_NEW")
        return
    out = pd.concat([book, pd.DataFrame(rows)], ignore_index=True)
    out.to_excel(MASTER, index=False)
    print("NBFP_ROWS", len(rows))


if __name__ == "__main__":
    main()
