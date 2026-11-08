import hashlib
from pathlib import Path
path = Path(r"D:\SHRI_JAI_SHRI_RAM\project_panels\ID_CARD_PROJECT\templates\IDCARD\BSM_PUBLIC_SCHOOL_CLEAN.png")
expected = "B4CEC57AF02B6CB92CDF2EB7262EB5E3F5582207BC23A29D578BA694D707E956"
if not path.is_file():
    print("CLEAN_ALREADY_GONE")
else:
    digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    if digest != expected:
        raise SystemExit("DO_NOT_DELETE " + digest)
    path.unlink()
    print("CLEAN_REMOVED")