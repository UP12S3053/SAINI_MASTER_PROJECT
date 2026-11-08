"""Option C fail-closed Gate with independent live sink read-back."""
from journal import load_journal, payload_fingerprint
from sink_verifier import verify_sinks

REQUIRED_SINKS = {"excel", "raw_ocr", "csv"}

def authorize(journal_path, *, expected_batch_id, expected_school_code, expected_fingerprint):
    try:
        if not expected_batch_id or not expected_school_code or not expected_fingerprint:
            return False, "missing_expected_values"
        record = load_journal(journal_path)
        if record.get("state") != "COMPLETED": return False, "state_not_completed"
        if record.get("batch_id") != expected_batch_id: return False, "batch_id_mismatch"
        if str(record.get("school_code", "")).strip().upper() != str(expected_school_code).strip().upper(): return False, "school_mismatch"
        if record.get("content_fingerprint") != expected_fingerprint: return False, "fingerprint_mismatch"
        if record.get("recovery_required") or record.get("invalidated"): return False, "recovery_or_invalidated"
        if set((record.get("sinks") or {}).keys()) != REQUIRED_SINKS: return False, "sink_schema_invalid"
        if any((record.get("sinks") or {}).get(n, {}).get("state") != "verified" for n in REQUIRED_SINKS): return False, "sink_not_verified"
        verification = record.get("verification") or {}
        if verification.get("batch_id") != expected_batch_id: return False, "verification_batch_id_mismatch"
        if str(verification.get("school_code", "")).strip().upper() != str(expected_school_code).strip().upper(): return False, "verification_school_mismatch"
        if verification.get("content_fingerprint") != expected_fingerprint: return False, "verification_fingerprint_mismatch"
        rows = verification.get("expected_rows")
        if not isinstance(rows, list) or payload_fingerprint(rows) != expected_fingerprint: return False, "verification_payload_fingerprint_mismatch"
        ok, evidence = verify_sinks(verification)
        if not ok: return False, "independent_sink_verification_failed:" + str(evidence.get("failure", evidence.get("reason", "unknown")))
        if set(evidence) != REQUIRED_SINKS: return False, "independent_sink_evidence_incomplete"
        recorded = record.get("verification_evidence") or {}
        if set(recorded) != REQUIRED_SINKS: return False, "recorded_sink_evidence_incomplete"
        if recorded != evidence: return False, "recorded_sink_evidence_changed"
        return True, "authorized"
    except Exception:
        return False, "internal_error"
