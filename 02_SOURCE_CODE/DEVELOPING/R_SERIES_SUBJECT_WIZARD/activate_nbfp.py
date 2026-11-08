import sqlite3
conn = sqlite3.connect(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\paper_bank.db")
conn.execute("UPDATE school_accounts SET status='ACTIVE', activated=1 WHERE school_code='NBFP'")
conn.commit()
row = conn.execute("SELECT school_code, status, activated FROM school_accounts WHERE school_code='NBFP'").fetchone()
print("NOW", row)
