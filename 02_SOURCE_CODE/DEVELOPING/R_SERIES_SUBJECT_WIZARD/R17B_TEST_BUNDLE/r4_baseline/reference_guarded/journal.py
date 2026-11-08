"""Option C — Journal module (isolated candidate).

Atomic write + validation.
"""
import hashlib
import json
import math
import os
from pathlib import Path

ALLOWED_STATES = {
    "PREPARED", "APPROVED", "COMMITTING", "VERIFIED",
    "COMPLETED", "INCOMPLETE", "RECOVERY_REQUIRED"
}
REQUIRED_FIELDS = {
    "schema_version", "batch_id", "school_code",
    "content_fingerprint", "state", "sinks"
}
REQUIRED_SINKS = {"excel", "raw_ocr", "csv"}

def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()

def payload_fingerprint(rows) -> str:
    canonical = [
        {str(key): _cell_text(value) for key, value in sorted(row.items(), key=lambda item: str(item[0]))}
        for row in rows
    ]
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_journal(record: dict) -> None:
    if not isinstance(record, dict):
        raise ValueError("journal must be a dict")
    if record.get("schema_version") != 2:
        raise ValueError(f"unsupported journal schema_version: {record.get('schema_version')!r}")
    missing = REQUIRED_FIELDS - record.keys()
    if missing:
        raise ValueError(f"missing fields: {missing}")
    if record["state"] not in ALLOWED_STATES:
        raise ValueError(f"invalid state: {record['state']}")
    if not record["batch_id"] or not record["school_code"] or not record["content_fingerprint"]:
        raise ValueError("batch_id, school_code and content_fingerprint required")
    sinks = record.get("sinks")
    if not isinstance(sinks, dict):
        raise ValueError("sinks must be a dict")
    if set(sinks) != REQUIRED_SINKS:
        raise ValueError(f"sink schema mismatch: expected {sorted(REQUIRED_SINKS)}")

def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)

def create_journal(path, record: dict) -> None:
    validate_journal(record)
    p = Path(path)
    if p.exists():
        raise FileExistsError(f"journal already exists: {p}")
    _atomic_write(p, record)
    loaded = load_journal(p)
    validate_journal(loaded)

def load_journal(path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"journal missing: {p}")
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    validate_journal(data)
    return data

def update_journal(path, updates: dict) -> None:
    p = Path(path)
    current = load_journal(p)
    # Never accept state-only completion or sink claims without evidence.
    requested_state = updates.get("state")
    if requested_state in {"VERIFIED", "COMPLETED"}:
        raise ValueError("verified/completed requires independent real-sink read-back evidence")
    requested_sinks = updates.get("sinks")
    if isinstance(requested_sinks, dict):
        for sink_name, sink_value in requested_sinks.items():
            sink_state = sink_value.get("state") if isinstance(sink_value, dict) else sink_value
            if sink_state == "verified":
                raise ValueError("sink=verified requires independent real-sink read-back evidence")
    current.update(updates)
    validate_journal(current)
    _atomic_write(p, current)
    loaded = load_journal(p)
    validate_journal(loaded)


def mark_recovery_required(path, reason: str) -> None:
    """Atomically leave an incomplete batch visibly blocked for recovery."""
    p = Path(path)
    current = load_journal(p)
    current["state"] = "RECOVERY_REQUIRED"
    current["recovery_required"] = True
    current["failure_reason"] = str(reason)[:1000]
    _atomic_write(p, current)
    validate_journal(load_journal(p))


def complete_journal(path, verification: dict) -> None:
    """Mark complete only after the independent verifier reopens all three data sinks."""
    from sink_verifier import verify_sinks
    p = Path(path)
    current = load_journal(p)
    if current.get("state") not in {"PREPARED", "APPROVED", "COMMITTING"}:
        raise ValueError("journal is not in a completable state")
    if verification.get("batch_id") != current.get("batch_id"):
        raise ValueError("verification batch_id does not match journal")
    if str(verification.get("school_code", "")).strip().upper() != str(current.get("school_code", "")).strip().upper():
        raise ValueError("verification school_code does not match journal")
    if verification.get("content_fingerprint") != current.get("content_fingerprint"):
        raise ValueError("verification fingerprint does not match journal")
    rows = verification.get("expected_rows")
    if not isinstance(rows, list) or payload_fingerprint(rows) != current.get("content_fingerprint"):
        raise ValueError("verification payload fingerprint mismatch")
    ok, evidence = verify_sinks(verification)
    if not ok or set(evidence) != REQUIRED_SINKS:
        raise ValueError(f"independent sink read-back verification failed: {evidence}")
    current["verification"] = verification
    current["verification_evidence"] = evidence
    current["sinks"] = {name: evidence[name] for name in ("excel", "raw_ocr", "csv")}
    current["state"] = "COMPLETED"
    current["recovery_required"] = False
    _atomic_write(p, current)
    validate_journal(load_journal(p))


def complete_recovered_journal(path, verification: dict, *, approval_evidence=None) -> None:
    """Finalize a RECOVERY_REQUIRED journal only after live sinks independently verify.

    This operation updates the journal only; it never writes to Excel, RAW OCR, or CSV.
    """
    from sink_verifier import verify_sinks
    p = Path(path)
    current = load_journal(p)
    if current.get("state") != "RECOVERY_REQUIRED" or not current.get("recovery_required"):
        raise ValueError("journal is not marked RECOVERY_REQUIRED")
    if current.get("invalidated"):
        raise ValueError("invalidated journal cannot be recovered")
    if verification.get("batch_id") != current.get("batch_id"):
        raise ValueError("verification batch_id does not match journal")
    if str(verification.get("school_code", "")).strip().upper() != str(current.get("school_code", "")).strip().upper():
        raise ValueError("verification school_code does not match journal")
    if verification.get("content_fingerprint") != current.get("content_fingerprint"):
        raise ValueError("verification fingerprint does not match journal")
    rows = verification.get("expected_rows")
    if not isinstance(rows, list) or payload_fingerprint(rows) != current.get("content_fingerprint"):
        raise ValueError("verification payload fingerprint mismatch")
    ok, evidence = verify_sinks(verification)
    if not ok or set(evidence) != REQUIRED_SINKS:
        raise ValueError(f"recovery sink read-back verification failed: {evidence}")
    if any(evidence.get(name, {}).get("state") != "verified" for name in REQUIRED_SINKS):
        raise ValueError(f"recovery sink state is not verified: {evidence}")
    current["verification"] = verification
    current["verification_evidence"] = evidence
    current["sinks"] = {name: evidence[name] for name in ("excel", "raw_ocr", "csv")}
    if approval_evidence is not None:
        current["approval_evidence"] = approval_evidence
    current["state"] = "COMPLETED"
    current["recovery_required"] = False
    current["recovered_journal_only"] = True
    _atomic_write(p, current)
    validate_journal(load_journal(p))
