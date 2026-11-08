"""Option C — Identity module (isolated candidate).

School: trim + uppercase
UID: outer trim only (preserve punctuation, case, leading zeros)
"""

def normalize_school(value):
    if value is None:
        return ""
    return str(value).strip().upper()

def normalize_uid(value):
    if value is None:
        return ""
    return str(value).strip()

def make_composite_key(school, uid):
    s = normalize_school(school)
    u = normalize_uid(uid)
    if not s or not u:
        raise ValueError("Missing school code or student UID")
    return (s, u)

def keys_equal(key1, key2):
    return key1 == key2
