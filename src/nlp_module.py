# === nlp_module.py / ecode_extractor.py ===
import re, os, csv, unicodedata
from pathlib import Path
from typing import List, Tuple, Dict, Optional

USE_CSV_SYNONYMS = False  # có thể bật nếu muốn dùng synonyms CSV


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
    res, words = [], tokenize_norm(text)
    if not words:
        return res
    for syn_norm, ecode in mapping_norm.items():
        toks = syn_norm.split()
        if len(toks) >= 2:
            n = len(toks)
            ref = " ".join(toks)
            md = max_allowed_dist(ref)
            for i in range(0, len(words) - n + 1):
                win = " ".join(words[i : i + n])
                dist = damerau_lev(win, ref, md)
                if dist <= md:
                    res.append((syn_norm, ecode, dist))
                    break
        else:
            ref = toks[0]
            md = max_allowed_dist(ref)
            for tok in words:
                dist = damerau_lev(tok, ref, md)
                if dist <= md:
                    res.append((syn_norm, ecode, dist))
                    break
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
    "b": "8",
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


def in_range(d: str) -> bool:
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


def extract_codes(text: str, csv_path: Optional[str] = None) -> List[str]:
    if is_units_only_line(text):
        return []

    if csv_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        c1 = os.path.join(script_dir, "E_INS.csv")
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

    # 2) E / INS + số
    pat_prefixed = re.compile(
        rf"\b(?P<prefix>E|INS)\s*-?\s*(?P<d>{DIGITLIKE})(?P<let>[A-Za-z]?)\s*(?:\((?P<rom>{ROMAN_OK})\))?\b",
        re.IGNORECASE,
    )
    for m in pat_prefixed.finditer(text):
        dlike = m.group("d")
        if count_real_digits(dlike) < 1:
            continue
        d = to_digits(dlike)
        if not d or not in_range(d):
            continue
        prefix = m.group("prefix").upper()
        let = (m.group("let") or "").lower()
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

    safe = []
    for c in stripped:
        if re.fullmatch(r"[0-9]{3,4}[a-z]*(\((?:i|ii|iii|iv|v|vi|vii|viii|ix)\))?", c):
            safe.append(c.lower())

    return sorted(set(safe))


def extract_ecodes_from_text(text: str, csv_path: Optional[str] = None) -> List[str]:
    if csv_path is None:
        script_dir = Path(__file__).resolve().parent
        candidates = [
            script_dir / "E_INS.csv",
            Path.cwd() / "data" / "processed" / "E_INS.csv",
            Path.cwd() / "E_INS.csv",
        ]
        for p in candidates:
            if p.exists():
                csv_path = str(p)
                break
        else:
            csv_path = None

    return extract_codes(text, csv_path=csv_path)