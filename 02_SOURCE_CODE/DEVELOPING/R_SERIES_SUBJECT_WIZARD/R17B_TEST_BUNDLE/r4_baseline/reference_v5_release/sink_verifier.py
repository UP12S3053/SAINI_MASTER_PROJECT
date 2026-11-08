"""Independent read-back verifier for Option C batch sinks.

Fail-closed checks against the current configured files. It does not trust the
journal's sink-state strings as proof of payload correctness.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ALIASES = {
    "student_name": ("student_name",),
    "class": ("class",),
    "school_code": ("school_code",),
    "mob_number": ("mob_number", "mobile"),
    "address": ("address",),
    "father_name": ("father_name",),
    "student_unique_id": ("student_unique_id", "unique_id"),
    "mother_name": ("mother_name",),
}
# These are the student-database fields the current Excel updater is allowed to
# populate. Scan-only metadata remains in the Raw OCR sink, not the student DB.
EXCEL_FIELDS = (
    "school_code", "student_unique_id", "student_name", "father_name",
    "class", "address", "mob_number", "source",
)


def _norm(value):
    return "" if value is None or pd.isna(value) else str(value).strip()


def _key(row):
    return (
        _norm(row.get("school_code")).upper(),
        _norm(row.get("student_unique_id") or row.get("unique_id")).upper(),
    )


def _column_map(columns):
    return {str(column).strip().lower(): column for column in columns}


def _actual_column(columns, logical):
    lower = _column_map(columns)
    return next((lower[name.lower()] for name in ALIASES.get(logical, (logical,))
                 if name.lower() in lower), None)


def _matches_expected(actual, expected, fields, columns):
    for logical in fields:
        column = _actual_column(columns, logical)
        if column is None:
            return False, f"required_column_missing:{logical}"
        if _norm(actual.get(column, "")) != _norm(expected.get(logical, "")):
            return False, f"payload_mismatch:{logical}"
    return True, "matched"


def verify_sinks(config):
    rows = config.get("expected_rows") or []
    school = str(config.get("school_code") or "").strip().upper()
    kind = str(config.get("kind") or "slip")
    if not isinstance(rows, list) or not rows or not school:
        return False, {"reason": "missing_expected_rows_or_school"}
    if any(not isinstance(row, dict) for row in rows):
        return False, {"reason": "expected_rows_schema_invalid"}
    expected_keys = [_key(row) for row in rows]
    if any(not uid or sc != school for sc, uid in expected_keys):
        return False, {"reason": "expected_identity_invalid_or_wrong_school"}
    if len(set(expected_keys)) != len(expected_keys):
        return False, {"reason": "duplicate_expected_composite_keys"}

    evidence = {}
    try:
        # Excel: reopen the configured workbook and verify each unique batch key
        # plus every expected field the updater is allowed to write.
        excel_path = Path(config["excel_path"])
        if not excel_path.is_file():
            raise RuntimeError("excel_missing")
        excel = pd.read_excel(excel_path, dtype=str).fillna("")
        excel_columns = _column_map(excel.columns)
        if "school_code" not in excel_columns or "student_unique_id" not in excel_columns:
            raise RuntimeError("excel_identity_headers_missing")
        for logical in EXCEL_FIELDS:
            if any(logical in row for row in rows) and _actual_column(excel.columns, logical) is None:
                raise RuntimeError(f"excel_required_column_missing:{logical}")
        excel_records = excel.to_dict("records")
        excel_expected_rows = config.get("excel_expected_rows")
        snapshot_fingerprint = config.get("excel_snapshot_fingerprint")
        if excel_expected_rows is not None:
            if not isinstance(excel_expected_rows, list) or len(excel_expected_rows) != len(rows):
                raise RuntimeError("excel_snapshot_schema_invalid")
            canonical = [{str(k): _norm(v) for k, v in sorted(r.items(), key=lambda item: str(item[0]))}
                         for r in excel_expected_rows]
            import hashlib, json
            actual_snapshot_fingerprint = hashlib.sha256(json.dumps(
                canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            if not snapshot_fingerprint or actual_snapshot_fingerprint != snapshot_fingerprint:
                raise RuntimeError("excel_snapshot_fingerprint_mismatch")
        else:
            # Compatibility for low-level unit tests/legacy journals. Production
            # completion path always records the batch-bound post-write snapshot.
            excel_expected_rows = rows
        for expected, key in zip(excel_expected_rows, expected_keys):
            if _key(expected) != key:
                raise RuntimeError("excel_snapshot_identity_mismatch")
            matches = [r for r in excel_records if _key({
                "school_code": r.get(excel_columns["school_code"], ""),
                "student_unique_id": r.get(excel_columns["student_unique_id"], ""),
            }) == key]
            if len(matches) != 1:
                raise RuntimeError("excel_batch_identity_missing_or_duplicate")
            fields = [field for field in EXCEL_FIELDS if field in expected]
            ok, reason = _matches_expected(matches[0], expected, fields, excel.columns)
            if not ok:
                raise RuntimeError("excel_" + reason)
        evidence["excel"] = {"state": "verified", "path": str(excel_path), "batch_keys": len(expected_keys)}
    except Exception as exc:
        evidence["excel"] = {"state": "unverified", "error": str(exc) or exc.__class__.__name__}
    try:
        # Raw OCR/correction: require every expected column and exact current-batch
        # payload, including correction metadata where supplied.
        raw_path = Path(config["raw_path"])
        if not raw_path.is_file():
            raise RuntimeError("raw_sink_missing")
        raw = pd.read_excel(raw_path, dtype=str).fillna("")
        raw_columns = _column_map(raw.columns)
        batch_column = raw_columns.get("_optionc_batch_id")
        batch_id = str(config.get("batch_id") or "").strip()
        if not batch_column or not batch_id:
            raise RuntimeError("raw_sink_batch_identity_missing")
        for expected in rows:
            for field in expected:
                if field.strip().lower() not in raw_columns:
                    raise RuntimeError(f"raw_sink_required_column_missing:{field}")
        raw_records = raw.to_dict("records")
        for expected, key in zip(rows, expected_keys):
            candidates = [r for r in raw_records if _key({
                "school_code": r.get(raw_columns.get("school_code", ""), ""),
                "student_unique_id": r.get(raw_columns.get("student_unique_id", raw_columns.get("unique_id", "")), ""),
            }) == key and _norm(r.get(batch_column, "")) == batch_id]
            exact = []
            for candidate in candidates:
                if all(_norm(candidate.get(raw_columns[field.lower()], "")) == _norm(value)
                       for field, value in expected.items()):
                    exact.append(candidate)
            if len(exact) != 1:
                raise RuntimeError("raw_sink_exact_payload_missing_mismatched_or_duplicate")
        evidence["raw_ocr"] = {"state": "verified", "path": str(raw_path), "payload_rows": len(rows)}
    except Exception as exc:
        evidence["raw_ocr"] = {"state": "unverified", "error": str(exc) or exc.__class__.__name__}
    try:
        # CSV: every expected mapped field must have a schema column; one exact
        # identity row per batch record, and all mapped payload values must match.
        csv_path = Path(config["csv_path"])
        if not csv_path.is_file() or csv_path.stat().st_size == 0:
            raise RuntimeError("csv_sink_missing_or_empty")
        csv = pd.read_csv(csv_path, dtype=str, keep_default_na=False, low_memory=False)
        csv_columns = _column_map(csv.columns)
        if "school_code" not in csv_columns or not ("student_unique_id" in csv_columns or "unique_id" in csv_columns):
            raise RuntimeError("csv_identity_headers_missing")
        csv_uid_column = csv_columns.get("student_unique_id", csv_columns.get("unique_id"))
        csv_expected_rows = config.get("csv_expected_rows")
        csv_snapshot_fingerprint = config.get("csv_snapshot_fingerprint")
        if csv_expected_rows is not None:
            if not isinstance(csv_expected_rows, list) or len(csv_expected_rows) != len(rows):
                raise RuntimeError("csv_snapshot_schema_invalid")
            canonical = [{str(k): _norm(v) for k, v in sorted(r.items(), key=lambda item: str(item[0]))}
                         for r in csv_expected_rows]
            import hashlib, json
            actual_csv_snapshot_fingerprint = hashlib.sha256(json.dumps(
                canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")).hexdigest()
            if not csv_snapshot_fingerprint or actual_csv_snapshot_fingerprint != csv_snapshot_fingerprint:
                raise RuntimeError("csv_snapshot_fingerprint_mismatch")
        else:
            csv_expected_rows = rows
        mapped_fields = [field for field in ALIASES if any(field in row for row in csv_expected_rows)]
        for field in mapped_fields:
            if _actual_column(csv.columns, field) is None:
                raise RuntimeError(f"csv_required_column_missing:{field}")
        for expected, key in zip(csv_expected_rows, expected_keys):
            if _key(expected) != key:
                raise RuntimeError("csv_snapshot_identity_mismatch")
            matches = csv[(csv[csv_columns["school_code"]].map(lambda x: _norm(x).upper()) == key[0]) &
                          (csv[csv_uid_column].map(lambda x: _norm(x).upper()) == key[1])]
            if len(matches) != 1:
                raise RuntimeError("csv_batch_identity_missing_or_duplicate")
            actual = matches.iloc[0].to_dict()
            ok, reason = _matches_expected(actual, expected, mapped_fields, csv.columns)
            if not ok:
                raise RuntimeError("csv_" + reason)
        evidence["csv"] = {"state": "verified", "path": str(csv_path), "payload_rows": len(rows)}
    except Exception as exc:
        msg = str(exc) or exc.__class__.__name__
        state = "pending" if msg == "csv_sink_missing_or_empty" else "unverified"
        evidence["csv"] = {"state": state, "error": msg}
    ok = all(evidence.get(name, {}).get("state") == "verified" for name in ("excel", "raw_ocr", "csv"))
    if not ok:
        failures = []
        for name in ("excel", "raw_ocr", "csv"):
            sink = evidence.get(name, {})
            if sink.get("state") != "verified":
                failures.append(f"{name}:{sink.get('error', 'unverified')}")
        csv_error = evidence.get("csv", {}).get("error")
        evidence["failure"] = "csv_sink_missing_or_empty" if csv_error == "csv_sink_missing_or_empty" else ";".join(failures)
    return ok, evidence
