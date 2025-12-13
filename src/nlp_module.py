# === nlp_module.py / ecode_extractor.py ===
import re, os, csv, unicodedata
from pathlib import Path
from typing import List, Tuple, Dict, Optional

USE_CSV_SYNONYMS = True  # có thể bật nếu muốn dùng synonyms CSV

# === NEW (theo yêu cầu): chỉ đọc 1 file CSV cố định ===
MASTER_CSV_PATH = r"D:\Hk7\KhoaLuan\ECODESAFETY\data\processed\ecodes_master.csv"

def norm(s: str) -> str:
    s = (s or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", s)


def collapse_non_alnum_to_space(s: str) -> str:
    return re.sub(r"[^0-9a-z]+", " ", s)


def tokenize_norm(s: str) -> List[str]:
    return [t for t in collapse_non_alnum_to_space(norm(s)).split() if t]


def load_mapping(csv_path: str, list_delim: str = ",") -> Tuple[Dict[str, str], List[str]]:
    mapping, synonyms_raw = {}, []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ecode = (row.get("ecode") or "").strip().upper()
            raw = row.get("synonyms") or ""
            for kw in raw.split(list_delim):
                kw = kw.strip()
                if not kw:
                    continue
                mapping[norm(kw)] = ecode
                synonyms_raw.append(kw)
    return mapping, synonyms_raw


def damerau_lev(a: str, b: str, max_dist: int = 2) -> int:
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return max_dist + 1
    prev2 = list(range(lb + 1))
    prev1 = [0] * (lb + 1)
    curr = [0] * (lb + 1)
    for i in range(1, la + 1):
        curr[0] = i
        row_min = curr[0]
        ai = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ai == b[j - 1] else 1
            curr[j] = min(prev1[j - 1] + cost, curr[j - 1] + 1, prev1[j] + 1)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                curr[j] = min(curr[j], prev2[j - 2] + 1)
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_dist:
            return max_dist + 1
        prev2, prev1, curr = prev1, curr, [0] * (lb + 1)
    return prev1[lb]


def max_allowed_dist(term: str) -> int:
    return 1 if len(term) <= 6 else 2


def fuzzy_find_synonyms(text: str, mapping_norm: Dict[str, str]) -> List[Tuple[str, str, int]]:
    """
    EXACT MATCH VERSION — đọc đúng hoàn toàn synonym từ CSV.
    Không fuzzy, không khoảng cách, chỉ nhận khi khớp 100%.
    dist = 0 luôn.
    """
    res = []
    text_norm = norm(text)

    # tách từ đã chuẩn hoá
    words = tokenize_norm(text_norm)
    if not words:
        return res

    text_join = " ".join(words)

    for syn_norm, ecode in mapping_norm.items():
        toks = syn_norm.split()

        # synonym có nhiều từ → match chuỗi
        if len(toks) >= 2:
            if syn_norm in text_join:
                res.append((syn_norm, ecode, 0))
        else:
            # synonym 1 từ → match từng token
            if syn_norm in words:
                res.append((syn_norm, ecode, 0))

    return res



DIGITLIKE = r"[0-9A-Za-z|!]{3,4}"
DIGITMAP = {
    "o": "0",
    "O": "0",
    "q": "0",
    "Q": "0",
    "l": "1",
    "I": "1",
    "i": "1",
    "|": "1",
    "!": "1",
    "z": "2",
    "Z": "2",
    "s": "5",
    "S": "5",
    "b": "6",
    "B": "8",
}


def to_digits(s: str) -> str:
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(ch)
        elif ch in DIGITMAP:
            out.append(DIGITMAP[ch])
        else:
            return ""
    return "".join(out)


def count_real_digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def in_range(d: str) -> bool:    #222
    try:
        n = int(d)
        return 100 <= n <= 1521
    except:
        return False


ROMAN_OK = r"(?:i|ii|iii|iv|v|vi|vii|viii|ix)"

SPACE_UNITS = r"(?:g|mg|kg|l|ml)\b"
NOSPACE_UNITS = r"(?:kcal|cal|kj|joule|oz|lb|ug|µg|mcg)\b"

UNIT_NEAR = [
    "khoi luong",
    "khoi luong tinh",
    "trong luong",
    "net weight",
    "net wt",
    "weight",
    "gia tri dinh duong",
    "nutrition",
    "nutritional",
    "energy",
    "protein",
    "fat",
    "carb",
    "sugar",
    "sodium",
    "salt",
]


def is_unit_context(text: str, start_idx: int, end_idx: int) -> bool:
    before = norm(text[max(0, start_idx - 28) : start_idx])
    if any(kw in before for kw in UNIT_NEAR):
        return True
    after = norm(text[end_idx : end_idx + 8])
    if re.match(rf"^\s+{SPACE_UNITS}", after):
        return True
    after_long = norm(text[end_idx : end_idx + 10])
    if re.match(rf"^\s*{NOSPACE_UNITS}", after_long):
        return True
    around = norm(text[max(0, start_idx - 12) : min(len(text), end_idx + 12)])
    if re.search(r"(?:per|/)\s*100\s*g\b", around):
        return True
    return False


def is_units_only_line(text: str) -> bool:
    t = norm(text)
    t = re.sub(rf"\b\d+\s+{SPACE_UNITS}", "", t)
    t = re.sub(rf"\b\d+\s*{NOSPACE_UNITS}", "", t)
    t = re.sub(r"[0-9\s;:.,()/]+", "", t)
    return t.strip() == ""


def _strip_prefix_and_flatten(code: str) -> str:
    # Bỏ E/INS ở đầu, giữ phần số + chữ + (roman)
    core = re.sub(r"^(?:E|INS)\s*-?", "", code, flags=re.IGNORECASE)
    return core


# === NEW (theo yêu cầu): đọc cột ins để lọc kết quả cuối ===
_ALLOWED_INS_CACHE: Optional[set] = None

def _canon_ins(s: str) -> str:
    # chuẩn hoá để so khớp: lower + bỏ khoảng trắng
    return re.sub(r"\s+", "", (s or "").strip().lower())

def _load_allowed_ins_set(csv_path: str) -> set:
    global _ALLOWED_INS_CACHE
    if _ALLOWED_INS_CACHE is not None:
        return _ALLOWED_INS_CACHE

    allowed = set()
    try:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ins_val = row.get("ins")
                if ins_val is None:
                    continue
                ins_norm = _canon_ins(ins_val)
                if ins_norm:
                    allowed.add(ins_norm)
    except:
        allowed = set()

    _ALLOWED_INS_CACHE = allowed
    return allowed


# === NEW (theo yêu cầu): đọc cột name + name_vn -> trả về ins ===
_NAME_INS_CACHE: Optional[Dict[str, str]] = None

def _canon_phrase(s: str) -> str:
    # chuẩn hoá phrase để match trong text (bỏ dấu + ký tự lạ + chuẩn hoá khoảng trắng)
    return " ".join(tokenize_norm(s))

def _load_name_ins_map(csv_path: str) -> Dict[str, str]:
    global _NAME_INS_CACHE
    if _NAME_INS_CACHE is not None:
        return _NAME_INS_CACHE

    mp: Dict[str, str] = {}
    try:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ins_val = (row.get("ins") or "").strip()
                if not ins_val:
                    continue

                # đọc 2 cột name và name_vn
                n1 = (row.get("name") or "").strip()
                n2 = (row.get("name_vn") or "").strip()

                for nm in (n1, n2):
                    k = _canon_phrase(nm)
                    if not k:
                        continue
                    # nếu trùng key, giữ ins đầu tiên (không thay đổi logic khác)
                    if k not in mp:
                        mp[k] = ins_val.strip()
    except:
        mp = {}

    _NAME_INS_CACHE = mp
    return mp


def extract_codes(text: str, csv_path: Optional[str] = None) -> List[str]:
    # === UPDATE (theo yêu cầu): chỉ loại "100 g" (có space), còn "100g" vẫn cho đi tiếp để lọc bằng CSV(ins) ===
    if is_units_only_line(text) and not re.fullmatch(
        r"\s*[0-9]{3,4}[a-z]*(\((?:i|ii|iii|iv|v|vi|vii|viii|ix)\))?\s*",
        text,
        re.IGNORECASE,
    ):
        return []

    if csv_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        c1 = os.path.join(script_dir, "ecode_dict_clean.csv")
        csv_path = c1 if os.path.exists(c1) else None

    found = set()

    # 1) Synonyms (nếu bật)
    if USE_CSV_SYNONYMS and csv_path and os.path.exists(csv_path):
        mapping_norm, _ = load_mapping(csv_path)
        fuzzy_hits = fuzzy_find_synonyms(text, mapping_norm)
        best_by_code = {}
        for syn_norm, e, dist in fuzzy_hits:
            if not (isinstance(e, str) and e.upper().startswith("E")):
                continue
            digits = "".join(ch for ch in e[1:] if ch.isdigit())
            if not (digits and in_range(digits)):
                continue
            cur = best_by_code.get(e)
            if cur is None or dist < cur[1] or (dist == cur[1] and len(syn_norm) > len(cur[0])):
                best_by_code[e] = (syn_norm, dist)
        if best_by_code:
            best_dist = min(dist for (_, dist) in best_by_code.values())
            for e, (syn_norm, dist) in best_by_code.items():
                if dist <= best_dist + 1:
                    found.add("E" + e[1:].lower())

    # === NEW (theo yêu cầu): match theo cột name + name_vn, nếu trùng thì trả về ins tương ứng ===
    if csv_path and os.path.exists(csv_path):
        name_map = _load_name_ins_map(csv_path)
        if name_map:
            words = tokenize_norm(text)
            if words:
                text_join = " ".join(words)
                for k, ins_val in name_map.items():
                    toks = k.split()
                    if len(toks) >= 2:
                        if k in text_join:
                            found.add("INS" + ins_val.strip().lower())
                    else:
                        if k in words:
                            found.add("INS" + ins_val.strip().lower())

    # 2) E / INS + số
    pat_prefixed = re.compile(
        rf"\b(?P<prefix>E|INS)\s*-?\s*(?P<d>{DIGITLIKE})(?P<let>[A-Za-z]?)\s*(?:\((?P<rom>{ROMAN_OK})\))?(?=$|[^A-Za-z0-9])",
        re.IGNORECASE,
    )
    for m in pat_prefixed.finditer(text):
        dlike = m.group("d")
        if count_real_digits(dlike) < 1:
            continue

        d = to_digits(dlike)
        let = (m.group("let") or "").lower()

        # === FIX: xử lý case INS160a(iv) khi dlike = "160a" và let rỗng ===
        if not d:
            if (not let) and dlike and dlike[-1].isalpha():
                d2 = to_digits(dlike[:-1])
                if d2:
                    d = d2
                    let = dlike[-1].lower()
            if not d:
                continue
        # === END FIX ===

        if not in_range(d):
            continue

        prefix = m.group("prefix").upper()
        rom = (m.group("rom") or "").lower()
        code = f"{prefix}{d}{let}"
        if rom:
            code += f"({rom})"
        found.add(code)


    # 3a) số + chữ + roman (160a(i))
    pat_letter_roman = re.compile(
        rf"(?<![A-Za-z0-9])(?P<d>{DIGITLIKE})(?P<let>[A-Za-z])\s*\(\s*(?P<rom>{ROMAN_OK})\s*\)",
        re.IGNORECASE,
    )
    for m in pat_letter_roman.finditer(text):
        dlike = m.group("d")
        if count_real_digits(dlike) < 2:
            continue
        d = to_digits(dlike)
        if not d or not in_range(d):
            continue
        if is_unit_context(text, m.start("d"), m.end("rom")):
            continue
        found.add(f"INS{d}{m.group('let').lower()}({m.group('rom').lower()})")

    # 3b) số + roman (211(ii))
    pat_roman = re.compile(
        rf"(?<![A-Za-z0-9])(?P<d>{DIGITLIKE})\s*\(\s*(?P<rom>{ROMAN_OK})\s*\)",
        re.IGNORECASE,
    )
    for m in pat_roman.finditer(text):
        dlike = m.group("d")
        if count_real_digits(dlike) < 2:
            continue
        d = to_digits(dlike)
        if not d or not in_range(d):
            continue
        if is_unit_context(text, m.start("d"), m.end("rom")):
            continue
        found.add(f"INS{d}({m.group('rom').lower()})")

    # 4) số trần
    pat_plain = re.compile(
        rf"(?<![A-Za-z0-9])(?P<d>{DIGITLIKE})(?![A-Za-z])(?!\s*\()(?=$|[^A-Za-z0-9])",
        re.IGNORECASE,
    )
    for m in pat_plain.finditer(text):
        dlike = m.group("d")
        if count_real_digits(dlike) < 2:
            continue
        d = to_digits(dlike)
        if not d or not in_range(d):
            continue
        if is_unit_context(text, m.start("d"), m.end("d")):
            continue
        found.add(f"INS{d}")



    # 5) số + chữ dính liền (160d, 407a, 551i...)
    pat_digit_letters = re.compile(
        rf"(?<![A-Za-z0-9])(?P<d>{DIGITLIKE})(?P<letters>[A-Za-z]+)\b"
        rf"(?!\s*\(\s*{ROMAN_OK}\s*\))",
        re.IGNORECASE,
    )
    for m in pat_digit_letters.finditer(text):
        dlike = m.group("d")
        if count_real_digits(dlike) < 2:
            continue
        d = to_digits(dlike)
        if not d or not in_range(d):
            continue
        letters = m.group("letters")
        if re.match(rf"^{NOSPACE_UNITS}", norm(letters)):
            continue
        found.add(f"INS{d}{letters.lower()}")

    # Bỏ E/INS, còn lại dạng '100', '160a(iv)'
    stripped = {_strip_prefix_and_flatten(c) for c in found}

    # === NEW (theo yêu cầu): lọc theo cột ins của CSV (exact match) ===
    allowed_ins = set()
    if csv_path and os.path.exists(csv_path):
        allowed_ins = _load_allowed_ins_set(csv_path)

    safe = []
    for c in stripped:
        if re.fullmatch(r"[0-9]{3,4}[a-z]*(\((?:i|ii|iii|iv|v|vi|vii|viii|ix)\))?", c):
            # chỉ giữ nếu tồn tại trong cột ins
            if allowed_ins and (_canon_ins(c) not in allowed_ins):
                continue
            safe.append(c.lower())

    return sorted(set(safe))


def extract_ecodes_from_text(text: str, csv_path: Optional[str] = None) -> List[str]:
    # === NEW (theo yêu cầu): bỏ candidates, đọc duy nhất 1 file cố định ===
    csv_path = MASTER_CSV_PATH
    return extract_codes(text, csv_path=csv_path)
