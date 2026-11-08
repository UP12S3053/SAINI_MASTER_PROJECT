"""Explicit, backup-first additive migration for a DEVELOPMENT database only."""
from __future__ import annotations
import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from subject_wizard_core import ensure_schema


def migrate(db_path: Path, development_root: Path) -> Path:
    db_path = db_path.resolve()
    development_root = development_root.resolve()
    if development_root not in db_path.parents:
        raise SystemExit(f"REFUSED: DB must be inside the designated DEVELOPMENT folder: {development_root}")
    if not db_path.is_file():
        raise SystemExit(f"REFUSED: database not found: {db_path}")
    backup_dir = development_root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"paper_bank_before_subject_migration_{stamp}.db"
    shutil.copy2(db_path, backup_path)
    # Verify backup opens and integrity-checks before touching the working DEVELOPMENT copy.
    with sqlite3.connect(backup_path) as check:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise SystemExit(f"REFUSED: backup integrity check failed: {result}")
    with sqlite3.connect(db_path) as conn:
        before = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        ensure_schema(conn)
        after = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if before != after:
            raise SystemExit("REFUSED: legacy question count changed during additive migration")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "subject_enrollments" not in tables:
            raise SystemExit("Migration failed: subject_enrollments table not found")
    print("DEVELOPMENT MIGRATION PASSED")
    print(f"Database: {db_path}")
    print(f"Verified backup: {backup_path}")
    print(f"Legacy question rows preserved: {before}")
    print("No subject was activated; no question rows were inserted.")
    return backup_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--development-root", required=True, type=Path)
    args = parser.parse_args()
    migrate(args.db, args.development_root)
