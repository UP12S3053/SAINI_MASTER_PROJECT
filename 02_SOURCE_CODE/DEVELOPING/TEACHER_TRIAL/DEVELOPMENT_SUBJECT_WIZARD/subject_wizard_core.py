"""Development-only subject enrollment primitives for the Saini Paper Setter.

This module never activates an enrollment. Callers must supply a DEVELOPMENT DB.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
ALLOWED_CLASSES = ("NURSERY", "LKG", "UKG", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")
ALLOWED_SUBJECTS = ("ENGLISH", "HINDI", "MATH", "SCIENCE", "SST", "EVS", "GK")
ALLOWED_CONTENT_TYPES = ("worksheet_images", "text_questions", "mixed")
ALLOWED_TEMPLATE_POLICIES = ("separate_master", "reuse_approved")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the wizard's additive table; do not alter legacy tables or rows."""
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subject_enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_id INTEGER NOT NULL,
            class_level TEXT NOT NULL,
            subject TEXT NOT NULL,
            subject_code TEXT NOT NULL,
            content_type TEXT NOT NULL,
            template_policy TEXT NOT NULL,
            template_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','READY','ACTIVE','RETIRED')),
            activated INTEGER NOT NULL DEFAULT 0 CHECK(activated IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT NOT NULL DEFAULT 'admin',
            schema_version INTEGER NOT NULL DEFAULT 1,
            UNIQUE(board_id, class_level, subject),
            UNIQUE(subject_code),
            FOREIGN KEY(board_id) REFERENCES boards(id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subject_enrollments_status ON subject_enrollments(status, activated)")
    conn.commit()


def normalize_subject_code(class_level: str, subject: str) -> str:
    cls = (class_level or "").strip().upper()
    sub = (subject or "").strip().upper()
    if cls not in ALLOWED_CLASSES:
        raise ValueError(f"Unsupported class: {cls!r}")
    if sub not in ALLOWED_SUBJECTS:
        raise ValueError(f"Unsupported subject: {sub!r}")
    return f"{cls}-{sub}"


def create_draft_enrollment(
    conn: sqlite3.Connection,
    *,
    board_code: str,
    class_level: str,
    subject: str,
    content_type: str = "worksheet_images",
    template_policy: str = "separate_master",
    template_root: str = "subject_templates",
    created_by: str = "admin",
) -> dict[str, Any]:
    """Insert a DRAFT enrollment only. Does not create questions or activate it."""
    code = normalize_subject_code(class_level, subject)
    board_code = (board_code or "").strip().upper()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Unsupported content type")
    if template_policy not in ALLOWED_TEMPLATE_POLICIES:
        raise ValueError("Unsupported template policy")
    if not re.fullmatch(r"[A-Z0-9_-]{2,16}", board_code):
        raise ValueError("Invalid board code")

    board = conn.execute("SELECT id, code FROM boards WHERE upper(code)=? AND active=1", (board_code,)).fetchone()
    if board is None:
        raise ValueError(f"Active board not found: {board_code}")

    # Relative, predictable path; reject traversal and absolute paths.
    relative = Path(template_root) / code
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Unsafe template path")
    template_path = relative.as_posix()
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.execute(
        """INSERT INTO subject_enrollments
        (board_id,class_level,subject,subject_code,content_type,template_policy,template_path,status,activated,created_by,schema_version)
        VALUES (?,?,?,?,?,?,?,'DRAFT',0,?,?)""",
        (board[0], class_level.strip().upper(), subject.strip().upper(), code, content_type,
         template_policy, template_path, (created_by or "admin")[:80], SCHEMA_VERSION),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "board_code": board_code,
        "class_level": class_level.strip().upper(),
        "subject": subject.strip().upper(),
        "subject_code": code,
        "content_type": content_type,
        "template_policy": template_policy,
        "template_path": template_path,
        "status": "DRAFT",
        "activated": False,
    }


def write_template_scaffold(template_root: Path, enrollment: dict[str, Any]) -> Path:
    """Create a minimal template metadata file; refuses to overwrite an existing one."""
    root = template_root.resolve()
    target_dir = (root / enrollment["subject_code"]).resolve()
    if target_dir != root and root not in target_dir.parents:
        raise ValueError("Template directory escapes the configured root")
    target_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = target_dir / "master_template.json"
    if metadata_path.exists():
        raise FileExistsError(f"Template metadata already exists: {metadata_path}")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "subject_code": enrollment["subject_code"],
        "board_code": enrollment["board_code"],
        "class_level": enrollment["class_level"],
        "subject": enrollment["subject"],
        "content_type": enrollment["content_type"],
        "template_policy": enrollment["template_policy"],
        "status": "DRAFT",
        "activated": False,
        "notes": "Development scaffold only. Add and validate approved template assets before activation.",
    }
    metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return metadata_path
