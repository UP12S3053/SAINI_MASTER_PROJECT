# -*- coding: utf-8 -*-
"""Prices belong to Saini. A school cannot change its own rate."""
import struct
import zipfile
from pathlib import Path

FIELDS = (
    ("master_rate", 10),
    ("copy_rate", 1),
    ("id_card_rate", 20),
    ("tie_small_rate", 0),
    ("tie_big_rate", 0),
    ("belt_rate", 0),
    ("diary_rate", 0),
)


def ensure(conn):
    conn.execute(
        """CREATE TABLE IF NOT EXISTS school_paper_rates (
            school_code TEXT PRIMARY KEY,
            master_rate INTEGER NOT NULL,
            copy_rate INTEGER NOT NULL
        )"""
    )
    have = {row[1] for row in conn.execute("PRAGMA table_info(school_paper_rates)")}
    for name, default in FIELDS:
        if name not in have:
            conn.execute(
                "ALTER TABLE school_paper_rates ADD COLUMN %s INTEGER NOT NULL DEFAULT %d" % (name, default)
            )
    conn.commit()


def _clean(school_code):
    code = (school_code or "").strip().upper()
    if not code or len(code) > 20:
        raise ValueError("School code is required")
    return code


def _number(value, label):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(label + " must be a whole number")
    if number < 0 or number > 500:
        raise ValueError(label + " must be from 0 to 500")
    return number


def all_rates(conn, school_code):
    ensure(conn)
    code = (school_code or "").strip().upper()
    row = conn.execute(
        "SELECT " + ",".join(name for name, _default in FIELDS) + " FROM school_paper_rates WHERE school_code=?",
        (code,),
    ).fetchone()
    if row is None:
        return {name: default for name, default in FIELDS}
    return {name: int(row[index]) for index, (name, _default) in enumerate(FIELDS)}


def rates_for(conn, school_code):
    data = all_rates(conn, school_code)
    return data["master_rate"], data["copy_rate"]


def item_rate(conn, school_code, item):
    data = all_rates(conn, school_code)
    key = item if item in data else item + "_rate"
    if key not in data:
        raise ValueError("Unknown rate")
    return data[key]


def set_rates(conn, school_code, values):
    ensure(conn)
    code = _clean(school_code)
    saved = {name: _number(values[name], name) for name, _default in FIELDS}
    columns = ["school_code"] + [name for name, _default in FIELDS]
    holders = ",".join("?" for _ in columns)
    updates = ",".join(name + "=excluded." + name for name, _default in FIELDS)
    conn.execute(
        "INSERT INTO school_paper_rates (" + ",".join(columns) + ") VALUES (" + holders + ") "
        "ON CONFLICT(school_code) DO UPDATE SET " + updates,
        [code] + [saved[name] for name, _default in FIELDS],
    )
    conn.commit()
    return code


def list_rates(conn):
    ensure(conn)
    return list(conn.execute(
        "SELECT school_code," + ",".join(name for name, _default in FIELDS) + " FROM school_paper_rates ORDER BY school_code"
    ))


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
