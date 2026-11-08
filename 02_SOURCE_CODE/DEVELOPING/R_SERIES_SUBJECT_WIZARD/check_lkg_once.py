import sqlite3
keys=("class","subject","board","std","grade")
paths=[(r"D:\\SAINI_TEACHER_TRIAL\\paper_bank.db","ORIGINAL"),(r"D:\\SAINI_TEACHER_TRIAL\\DEVELOPMENT_SUBJECT_WIZARD\\paper_bank.db","DEV")]
for path,label in paths:
 con=sqlite3.connect("file:"+path.replace(chr(92),"/")+"?mode=ro", uri=True)
 cols=[r[1] for r in con.execute("PRAGMA table_info(questions)")]
 print(label,"QCOLS",",".join(cols))
 for c in cols:
  if any(k in c.lower() for k in keys):
   rows=con.execute("SELECT [%s], COUNT(*) FROM questions GROUP BY 1 ORDER BY 2 DESC"%c).fetchall()
   print(label,c," ; ".join("%s=%s"%(a,b) for a,b in rows))
 if label=="DEV":
  print("ENROLL_COLS",",".join(r[1] for r in con.execute("PRAGMA table_info(subject_enrollments)")))
