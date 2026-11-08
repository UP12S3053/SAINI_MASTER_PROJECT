# -*- coding: utf-8 -*-
"""Select the first BSM row whose SCHOOLNAME is non-empty. Never saves the workbook."""
from pathlib import Path
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from config_validator import REQUIRED_FIELDS, header_positions, normalize_cell, resolve_header
from template_identity import inspect_selected_template


def _fail(status, error, **extra):
    result = {
        "success": False,
        "status": status,
        "error": error,
        "selected_school_code": "",
        "selected_excel_row": None,
        "selected_school_name": "",
        "selected_template_path": "",
        "selected_card_type": "",
        "selected_card_format": "",
        "fields": {},
        "duplicate_headers": {},
        "rejected_rows": [],
        "validation_errors": [error] if error else [],
    }
    result.update(extra)
    if "template" not in result:
        result["template"] = {}
    return result


def _row_field(row, positions, name):
    columns = positions.get(name, [])
    if not columns:
        return {"columns": [], "resolved": "", "ambiguous": False, "missing": True}
    found = resolve_header(row, columns)
    found["missing"] = False
    return found


def _problem(found, name):
    if found["missing"]:
        return f"required_header_missing:{name}"
    if found["ambiguous"]:
        return f"ambiguous_required_header:{name}"
    if not found["resolved"]:
        return f"required_value_empty:{name}"
    return ""


def load_school_config(workbook_path, school_code="BSM"):
    """Read Sheet1 in worksheet order and stop at the first eligible school row."""
    path = Path(workbook_path)
    target = normalize_cell(school_code).upper()
    if not target:
        return _fail("fail_closed", "school_code_missing")
    if not path.is_file():
        return _fail("fail_closed", "workbook_missing", workbook=str(path))
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            if "Sheet1" not in workbook.sheetnames:
                return _fail("fail_closed", "sheet1_missing", workbook=str(path))
            grid = [tuple(row) for row in workbook["Sheet1"].iter_rows(values_only=True)]
        finally:
            workbook.close()
    except (InvalidFileException, BadZipFile, OSError, ValueError, KeyError) as exc:
        return _fail("fail_closed", "workbook_unreadable", workbook=str(path), detail=exc.__class__.__name__)
    if not grid:
        return _fail("fail_closed", "workbook_empty", workbook=str(path))

    positions, blank_columns = header_positions(grid[0])
    duplicates = {name: columns for name, columns in positions.items() if len(columns) > 1}
    if "school_code" not in positions or "SCHOOLNAME" not in positions:
        return _fail(
            "fail_closed",
            "required_header_missing",
            workbook=str(path),
            duplicate_headers=duplicates,
            blank_header_columns=blank_columns,
        )

    rejected = []
    chosen = None
    for excel_row, row in enumerate(grid[1:], start=2):
        code = _row_field(row, positions, "school_code")
        if code["ambiguous"]:
            if any(item["normalized"].upper() == target for item in code["columns"]):
                return _fail(
                    "fail_closed",
                    "ambiguous_required_header:school_code",
                    workbook=str(path),
                    duplicate_headers=duplicates,
                    blank_header_columns=blank_columns,
                    rejected_rows=rejected,
                    validation_errors=["ambiguous_required_header:school_code", f"excel_row:{excel_row}"],
                )
            continue
        if code["resolved"].upper() != target:
            continue
        school_name = _row_field(row, positions, "SCHOOLNAME")
        if school_name["ambiguous"]:
            return _fail(
                "fail_closed",
                "ambiguous_required_header:SCHOOLNAME",
                workbook=str(path),
                duplicate_headers=duplicates,
                blank_header_columns=blank_columns,
                rejected_rows=rejected,
                validation_errors=["ambiguous_required_header:SCHOOLNAME", f"excel_row:{excel_row}"],
            )
        if not school_name["resolved"]:
            rejected.append({"excel_row": excel_row, "reason": "empty_schoolname"})
            continue
        chosen = (excel_row, row, school_name["resolved"])
        break

    if chosen is None:
        reason = "school_not_found" if not rejected else "no_eligible_schoolname"
        return _fail(
            "fail_closed",
            reason,
            workbook=str(path),
            duplicate_headers=duplicates,
            blank_header_columns=blank_columns,
            rejected_rows=rejected,
        )

    excel_row, row, school_name = chosen
    fields = {name: _row_field(row, positions, name) for name in positions}
    problems = [problem for name in REQUIRED_FIELDS if (problem := _problem(fields.get(name, _row_field(row, positions, name)), name))]
    if problems:
        return _fail(
            "fail_closed",
            problems[0],
            workbook=str(path),
            duplicate_headers=duplicates,
            blank_header_columns=blank_columns,
            rejected_rows=rejected + [{"excel_row": excel_row, "reason": problems[0]}],
            validation_errors=problems,
            fields=fields,
        )

    template_check = inspect_selected_template(fields["template"]["resolved"], school_name)
    template = template_check["template"]
    identity = template_check["identity"]
    card_type = fields["CARD"]["resolved"]
    card_format = fields["CARD_TYPE"]["resolved"]
    if not template["ok"] or not identity.get("ok"):
        error = template["error"] if not template["ok"] else identity["error"]
        return _fail(
            "fail_closed",
            error,
            workbook=str(path),
            selected_school_code=target,
            selected_excel_row=excel_row,
            selected_school_name=school_name,
            selected_template_path=fields["template"]["resolved"],
            selected_card_type=card_type,
            selected_card_format=card_format,
            fields=fields,
            duplicate_headers=duplicates,
            blank_header_columns=blank_columns,
            rejected_rows=rejected + [{"excel_row": excel_row, "reason": error}],
            validation_errors=[error],
            template=template,
            identity=identity,
        )

    return {
        "success": True,
        "status": "selected",
        "error": "",
        "workbook": str(path),
        "selected_school_code": target,
        "selected_excel_row": excel_row,
        "selected_school_name": school_name,
        "selected_template_path": fields["template"]["resolved"],
        "selected_card_type": card_type,
        "selected_card_format": card_format,
        "fields": fields,
        "duplicate_headers": duplicates,
        "blank_header_columns": blank_columns,
        "rejected_rows": rejected,
        "validation_errors": [],
        "template": template,
        "identity": identity,
    }
