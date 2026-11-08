from pathlib import Path
import py_compile
p=Path(r"D:\SAINI_TEACHER_TRIAL\DEVELOPMENT_SUBJECT_WIZARD\school_data.py")
t=p.read_text(encoding="utf-8")
old='            + \'<label>Student unique ID</label><input name="student_uid" required maxlength="20" value="\'\n            + _esc(lookup) + \'">\'\n            + \'<label>Subject</label>'
new='            + \'<input type="hidden" name="student_uid" value="\' + _esc(lookup) + \'">\'\n            + \'<label>Class</label><input value="\' + _esc(found[1] if found else \'\') + \'" readonly>\'\n            + \'<label>Subject</label>'
if t.count(old)!=1:
    raise SystemExit("ABORT "+str(t.count(old)))
u=t.replace(old,new,1)
tmp=p.with_name("school_data.marks_tmp")
chk=p.with_name("school_data.class_check.pyc")
tmp.write_text(u,encoding="utf-8",newline="\n")
try:
    py_compile.compile(str(tmp),cfile=str(chk),doraise=True)
finally:
    if chk.exists(): chk.unlink()
bak=Path(r"D:\SAINI_SUBJECT_WIZARD_PATCH\BACKUP_BEFORE_FIX\school_data_before_class_field.py")
bak.write_bytes(p.read_bytes())
p.write_text(u,encoding="utf-8",newline="\n")
tmp.unlink()
print("PATCH_OK")
print("class_field=yes")
print("second_id=hidden")
