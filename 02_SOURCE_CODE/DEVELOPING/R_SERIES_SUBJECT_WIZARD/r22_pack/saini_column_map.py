# -*- coding: utf-8 -*-
"""Explicit handling for duplicate configuration headers.

No column is authoritative. A duplicated tracked header cannot be read or
written until a caller names one exact column. This module never renames a
header, never merges columns, and never saves the live or R22 workbook.
"""
import os
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

LIVE_WORKBOOK = r"D:\SHRI_JAI_SHRI_RAM\project_panels\school_config_front.xlsx"
R22_WORKBOOK = r"D:\SAINI_SUBJECT_WIZARD_PATCH\SAINI_ID_DEV_R22\school_config_front.xlsx"
_LEGACY_F_PREFIX = "f:\\shri_jai_shri_ram"

TRACKED = (
    "ADDR_COLOR", "ADDR_SIZE", "FATHER_COLOR", "FATHER_FONT", "FATHER_PREFIX",
    "FATHER_SHOW", "FATHER_SIZE", "FATHER_X", "FATHER_Y", "M",
)
REFERENCE_COLUMNS = {
    "ADDR_COLOR": ("CP", "CW"),
    "ADDR_SIZE": ("CO", "CV"),
    "FATHER_COLOR": ("BE", "BS"),
    "FATHER_FONT": ("BC", "BQ"),
    "FATHER_PREFIX": ("BF", "BT"),
    "FATHER_SHOW": ("AZ", "BU"),
    "FATHER_SIZE": ("BD", "BR"),
    "FATHER_X": ("BA", "BO"),
    "FATHER_Y": ("BB", "BP"),
    "M": ("BW", "BX", "BY", "BZ", "CA"),
}


class AmbiguousHeaderError(RuntimeError):
    """A header occurs more than once and no exact column was approved."""


class ColumnMapError(RuntimeError):
    """The requested column does not match the workbook header."""


def _folded(path):
    return str(path).replace("/", "\\").casefold()


def reject_forbidden_path(path):
    folded = _folded(path)
    if folded.startswith(_LEGACY_F_PREFIX):
        raise ColumnMapError("Refusing legacy F: workbook path.")
    if folded == _folded(LIVE_WORKBOOK):
        raise ColumnMapError("Refusing live production workbook path.")
    return str(path)


def column_index(letter):
    number = 0
    for character in str(letter).strip().upper():
        if not ("A" <= character <= "Z"):
            raise ColumnMapError("Invalid column letter.")
        number = number * 26 + ord(character) - 64
    if number <= 0:
        raise ColumnMapError("Invalid column letter.")
    return number


def column_letter(number):
    text = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        text = chr(65 + remainder) + text
    return text


def header_positions(path, sheet_name=None):
    """Return header name to exact columns. Values below the header are not returned."""
    reject_forbidden_path(path)
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        if sheet_name and sheet_name not in book.sheetnames:
            raise ColumnMapError("Expected worksheet is missing.")
        sheet = book[sheet_name] if sheet_name else book[book.sheetnames[0]]
        row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), ())
    finally:
        book.close()
    found = {}
    for index, cell in enumerate(row, start=1):
        if cell is None or str(cell).strip() == "":
            continue
        found.setdefault(str(cell), []).append((column_letter(index), index))
    return found


def reference_differences(path, sheet_name=None):
    """Compare actual columns with the R20/R21 reference. This approves nothing."""
    found = header_positions(path, sheet_name)
    differences = []
    for name in TRACKED:
        actual = tuple(letter for letter, _index in found.get(name, []))
        if actual != REFERENCE_COLUMNS[name]:
            differences.append((name, actual, REFERENCE_COLUMNS[name]))
    return differences


def ambiguous_headers(path, sheet_name=None):
    found = header_positions(path, sheet_name)
    return [name for name in TRACKED if len(found.get(name, [])) > 1]


def assert_unambiguous(path, sheet_name=None):
    found = ambiguous_headers(path, sheet_name)
    if found:
        raise AmbiguousHeaderError("Ambiguous configuration headers: " + ",".join(found))


def load_guarded_config(path, sheet_name=None):
    """Load a workbook only when no tracked header is duplicated."""
    assert_unambiguous(path, sheet_name)
    if sheet_name:
        return pd.read_excel(path, sheet_name=sheet_name)
    return pd.read_excel(path)


def assert_writable(path, sheet_name=None):
    """Refuse a sheet write while a tracked header is ambiguous."""
    reject_forbidden_path(path)
    if _folded(path) == _folded(R22_WORKBOOK):
        raise ColumnMapError("Refusing to save the R22 development workbook.")
    assert_unambiguous(path, sheet_name)


def _sheet_rows(path, sheet_name):
    reject_forbidden_path(path)
    book = load_workbook(path, read_only=True, data_only=False)
    try:
        if sheet_name and sheet_name not in book.sheetnames:
            raise ColumnMapError("Expected worksheet is missing.")
        sheet = book[sheet_name] if sheet_name else book[book.sheetnames[0]]
        return [tuple(row) for row in sheet.iter_rows(values_only=True)]
    finally:
        book.close()


def _require_approved(path, excel_row, field, approved_letter, sheet_name=None):
    if field not in TRACKED:
        raise ColumnMapError("Field is not in the duplicate-header scope.")
    if not approved_letter:
        raise AmbiguousHeaderError("Explicit column required for " + field)
    if _folded(path) in (_folded(LIVE_WORKBOOK), _folded(R22_WORKBOOK)):
        raise ColumnMapError("Refusing explicit mapping on the live or R22 workbook.")
    rows = _sheet_rows(path, sheet_name)
    if not rows:
        raise ColumnMapError("Workbook header row is missing.")
    headers = rows[0]
    index = column_index(approved_letter)
    if index > len(headers):
        raise ColumnMapError("Approved column is outside the header row.")
    actual = "" if headers[index - 1] is None else str(headers[index - 1])
    if actual != field:
        raise ColumnMapError("Header at the approved column does not match the field.")
    if excel_row < 2 or excel_row > len(rows):
        raise ColumnMapError("Row is outside the worksheet.")
    row = rows[excel_row - 1]
    return row[index - 1] if index - 1 < len(row) else None


def read_explicit(path, excel_row, field, approved_letter, sheet_name=None):
    return _require_approved(path, excel_row, field, approved_letter, sheet_name)


def write_explicit(path, excel_row, field, new_value, approved_letter, sheet_name=None):
    """Write one approved blank cell. Formulas, headers, and filled cells stay unchanged."""
    if new_value is None or str(new_value).strip() == "":
        raise ColumnMapError("Blank value will not clear an existing cell.")
    _require_approved(path, excel_row, field, approved_letter, sheet_name)
    book = load_workbook(path, read_only=False, data_only=False)
    try:
        if sheet_name and sheet_name not in book.sheetnames:
            raise ColumnMapError("Expected worksheet is missing.")
        sheet = book[sheet_name] if sheet_name else book[book.sheetnames[0]]
        headers_before = tuple(cell.value for cell in sheet[1])
        index = column_index(approved_letter)
        if index > len(headers_before) or str(headers_before[index - 1]) != field:
            raise ColumnMapError("Header at the approved column does not match the field.")
        cell = sheet.cell(excel_row, index)
        if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
            raise ColumnMapError("Formula cell will not be overwritten.")
        if cell.value not in (None, ""):
            raise ColumnMapError("Existing non-empty cell will not be overwritten.")
        if sheet.protection.sheet and cell.protection.locked:
            raise ColumnMapError("Protected cell will not be overwritten.")
        cell.value = new_value
        if tuple(item.value for item in sheet[1]) != headers_before:
            raise ColumnMapError("Header row changed; workbook will not be saved.")
        book.save(path)
    finally:
        book.close()
