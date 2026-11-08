import hashlib, os, sqlite3
from datetime import datetime
from pathlib import Path

db = Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\paper_bank.db")
salt = os.urandom(16)
digest = hashlib.pbkdf2_hmac("sha256", b"NBFP2026", salt, 200000)
hashed = "pbkdf2_sha256$200000$" + salt.hex() + "$" + digest.hex()
conn = sqlite3.connect(db)
row = conn.execute("SELECT school_code FROM school_accounts WHERE school_code=?", ("NBFP",)).fetchone()
print("FOUND" if row else "NEW", row)
if row:
    conn.execute("UPDATE school_accounts SET password_hash=? WHERE school_code=?", (hashed, "NBFP"))
else:
    conn.execute(
        "INSERT INTO school_accounts (school_code, school_name, city, password_hash, status, activated, created_at) VALUES (?,?,?,?, 'DRAFT', 0, ?)",
        ("NBFP", "NEW BRIGHT FUTURE PUBLIC SCHOOL", "KAIRANA", hashed, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
conn.commit()
print("PASSWORD_SET NBFP2026")
