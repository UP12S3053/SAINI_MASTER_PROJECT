# -*- coding: utf-8 -*-
"""Paper prices belong to Saini. A school cannot change its own rate."""
import struct
import zipfile
from pathlib import Path


def ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_paper_rates (
            school_code TEXT PRIMARY KEY,
            master_rate INTEGER NOT NULL,
            copy_rate INTEGER NOT NULL
        )"""
    )
    conn.commit()


def rates_for(conn, school_code):
    ensure(conn)
    code = (school_code or "").strip().upper()
    row = conn.execute(
        "SELECT master_rate, copy_rate FROM school_paper_rates WHERE school_code=?",
        (code,),
    ).fetchone()
    if row is None:
        return 10, 1
    return int(row[0]), int(row[1])


def set_rates(conn, school_code, master_rate, copy_rate):
    ensure(conn)
    code = (school_code or "").strip().upper()
    if not code or len(code) > 20:
        raise ValueError("School code is required")
    master = int(master_rate)
    copy = int(copy_rate)
    if master < 0 or master > 500 or copy < 0 or copy > 500:
        raise ValueError("Rate must be from 0 to 500")
    conn.execute(
        """INSERT INTO school_paper_rates (school_code, master_rate, copy_rate)
        VALUES (?,?,?)
        ON CONFLICT(school_code) DO UPDATE SET
        master_rate=excluded.master_rate, copy_rate=excluded.copy_rate""",
        (code, master, copy),
    )
    conn.commit()
    return code, master, copy


def sheets_in_docx(path):
    path = Path(path)
    if not path.is_file():
        return 1
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        return 1
    full = 0
    strips = 0
    for name in archive.namelist():
        if not name.startswith("word/media/"):
            continue
        data = archive.read(name)
        height = 0
        if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
            height = struct.unpack(">I", data[20:24])[0]
        if height >= 1200:
            full += 1
        else:
            strips += 1
    sheets = full + ((strips + 4) // 5 if strips else 0)
    if sheets < 1:
        sheets = 1
    if sheets > 12:
        sheets = 12
    return sheets
