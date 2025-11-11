import csv, re

# ==========================================================
# 1) Đọc CSV (synonyms)
# ==========================================================
def load_mapping(csv_path: str, list_delim: str = ","):
    mapping = {}
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ecode = row["ecode"].strip().upper()
            raw = row.get("synonyms") or ""
            for kw in raw.split(list_delim):
                kw_norm = kw.strip().lower()
                if kw_norm:
                    mapping[kw_norm] = ecode
    return mapping


def build_synonym_regex(keys):
    escaped = [re.escape(k) for k in sorted(set(keys), key=len, reverse=True)]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE) if escaped else None


# ==========================================================
# 2) Regex đơn vị đo (để loại trừ)
# ==========================================================
def get_unit_suffix():
    units = [
        "g", "mg", "kg", "l", "ml",
        "mcg", "µg", "ug", "oz", "lb",
        "gram", "grams", "kilogram",
        "liter", "litre", "liters", "lít",
        "kcal", "cal", "joule", "kj"
    ]
    return r"(?:" + "|".join(units) + r")\b"


# ==========================================================
# 3) Chuẩn hoá E-code
# ==========================================================
def normalize_ecode_from_parts(digits: str, letter: str = "", roman: str = "") -> str:
    code = f"E{digits}"
    if letter:
        code += letter.upper()
    if roman:
        code += f"({roman.upper()})"
    return code


# ==========================================================
# 4) Regex nhận diện (đã mở rộng 3–4 chữ số)
# ==========================================================
def extract_regex_ecodes(text: str):
    UNIT_SUFFIX = get_unit_suffix()
    found = set()

    # --- 4.1) E|INS + 3–4 số + [a-l]? + (i|ii|iii)?
    pattern_e = re.compile(
        rf"""
        \b(?:E|INS)\s*-?\s*
        (?P<digits>[0-9]{{3,4}})
        (?P<let>[A-L]?)
        (?:\((?P<roman>i{{1,3}})\))?
        (?![A-Za-z]|(?:{UNIT_SUFFIX}))
        (?=$|[^A-Za-z0-9])
        """, re.IGNORECASE | re.VERBOSE
    )
    for m in pattern_e.finditer(text):
        code = normalize_ecode_from_parts(m.group("digits"), m.group("let"), m.group("roman") or "")
        found.add(code)

    # --- 4.2) La Mã i|ii|iii KHÔNG cần E/INS
    pattern_roman = re.compile(
        rf"""
        (?<![A-Za-z0-9])
        (?P<digits>[0-9]{{3,4}})
        (?:\(\s*(?P<roman1>i{{1,3}})\s*\)|(?P<roman2>i{{1,3}}))
        (?![A-Za-z]|(?:{UNIT_SUFFIX}))
        (?=$|[^A-Za-z0-9])
        """, re.IGNORECASE | re.VERBOSE
    )
    for m in pattern_roman.finditer(text):
        roman = m.group("roman1") or m.group("roman2") or ""
        found.add(normalize_ecode_from_parts(m.group("digits"), "", roman))

    # --- 4.3) Số đơn (180), (330), (1105)
    pattern_plain = re.compile(
        rf"""
        (?<![A-Za-z0-9])
        \(?\s*
        (?P<digits>[0-9]{{3,4}})
        (?!\s*(?:{UNIT_SUFFIX}))      # chặn đơn vị ngay sau số
        \s*\)?
        (?![A-Za-z]|(?:{UNIT_SUFFIX}))
        (?=$|[^A-Za-z0-9])
        """, re.IGNORECASE | re.VERBOSE
    )
    for m in pattern_plain.finditer(text):
        found.add(f"E{m.group('digits')}")

    # --- 4.4) Ngoặc nhiều số: (200,201,1105)
    pattern_multi = re.compile(
        rf"""
        \(
            \s*
            (?P<numbers>
                (?:[0-9]{{3,4}}(?!\s*(?:{UNIT_SUFFIX}))\s*,\s*)+[0-9]{{3,4}}(?!\s*(?:{UNIT_SUFFIX}))
            )
            \s*
        \)
        (?![A-Za-z]|(?:{UNIT_SUFFIX}))
        """, re.IGNORECASE | re.VERBOSE
    )
    for m in pattern_multi.finditer(text):
        for n in re.findall(r"[0-9]{3,4}", m.group("numbers")):
            found.add(f"E{n}")

    # 4.5) Ngoặc chứa NHIỀU E/INS: (INS 189, INS167b), (E100, E200), (INS 300, E200)
    pattern_ins_multi = re.compile(
        rf"""
        \(
            [^)]*?(?:E|INS)\s*[0-9]{{3,4}}[A-L]?(?:\(\s*i{{1,3}}\s*\))?[^)]*?
        \)
        """, re.IGNORECASE | re.VERBOSE
    )
    for m in pattern_ins_multi.finditer(text):
        inside = m.group(0)
        for md in re.finditer(r"(?:E|INS)\s*-?\s*([0-9]{3,4})([A-L]?)(?:\(\s*(i{1,3})\s*\))?",
                               inside, flags=re.IGNORECASE):
            digits, let, roman = md.group(1), md.group(2) or "", (md.group(3) or "")
            found.add(normalize_ecode_from_parts(digits, let, roman))

    return found

def extract_ecodes_from_text(text, csv_path="data/processed/ecode_dict_clean.csv"):
    mapping = load_mapping(csv_path)
    result = set()

    syn_pat = build_synonym_regex(mapping.keys())
    if syn_pat:
        for m in syn_pat.finditer(text.lower()):
            result.add(mapping[m.group(1).lower()])

    result |= extract_regex_ecodes(text)

    return sorted(result)