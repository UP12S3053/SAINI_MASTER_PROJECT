import hashlib, os, sqlite3
from datetime import datetime

CODE = "NBF"
NAME = "NEW BRIGHT FUTURE PUBLIC SCHOOL"
CITY = "MAMOUR"
PASSWORD = "NBF2026"

salt = os.urandom(16)
digest = hashlib.pbkdf2_hmac("sha256", PASSWORD.encode("utf-8"), salt, 200000)
hashed = "pbkdf2_sha256$200000$" + salt.hex() + "$" + digest.hex()
conn = sqlite3.connect(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\paper_bank.db")
row = conn.execute("SELECT school_code FROM school_accounts WHERE school_code=?", (CODE,)).fetchone()
if row:
    conn.execute("UPDATE school_accounts SET school_name=?, city=?, password_hash=? WHERE school_code=?", (NAME, CITY, hashed, CODE))
    print("UPDATED", CODE)
else:
    conn.execute(
        "INSERT INTO school_accounts (school_code, school_name, city, password_hash, status, activated, created_at) VALUES (?,?,?,?, 'DRAFT', 0, ?)",
        (CODE, NAME, CITY, hashed, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    print("CREATED", CODE)
conn.commit()
print("PASSWORD", PASSWORD)
