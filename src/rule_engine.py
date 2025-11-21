from pathlib import Path
import yaml

def evaluate_rules(facts, rules_path=None):
    """
    Áp dụng rule từ risk_rules.yaml cho dataset INS mới.
    facts gồm các key:
    - status_vn: 0 hoặc 1
    - adi: string/float
    - info: mô tả
    """

    # Tìm file YAML
    if rules_path is None:
        rules_path = Path(__file__).resolve().parent.parent / "rules" / "risk_rules.yaml"

    with open(rules_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # ----- Chuẩn hoá input -----

    # status_vn
    status_vn = facts.get("status_vn")
    try:
        status_vn = int(status_vn)
    except:
        status_vn = None

    # adi
    raw_adi = facts.get("adi")
    if raw_adi in (None, "", "nan", "NaN", "updating"):
        adi_val = None
    else:
        try:
            adi_val = float(raw_adi)
        except:
            adi_val = None

    # info
    info = facts.get("info", "")
    if not isinstance(info, str):
        info = str(info)

    # ------------------------------------------------------------
    # BẮT ĐẦU ÁP DỤNG RULE
    # ------------------------------------------------------------
    for rule_name in spec["priority"]:
        rule = spec["rules"][rule_name]
        cond = rule.get("if", {})
        ok = True

        # -----------------------------
        # status_vn_eq
        # -----------------------------
        if "status_vn_eq" in cond:
            if status_vn != cond["status_vn_eq"]:
                ok = False

        # -----------------------------
        # info_contains_any
        # -----------------------------
        if "info_contains_any" in cond:
            patterns = cond["info_contains_any"]
            info_lower = info.lower()

            if not any(p.lower() in info_lower for p in patterns):
                ok = False

        # -----------------------------
        # adi_lt
        # -----------------------------
        if "adi_lt" in cond:
            threshold = cond["adi_lt"]
            if adi_val is None or not (adi_val < threshold):
                ok = False

        # Nếu rule thỏa mãn
        if ok:
            return {
                "risk": rule["then"]["risk"],
                "reason": rule["then"]["reason"],
                "rule": rule_name
            }

    # Nếu không rule nào khớp → mặc định mức 1
    return {
        "risk": 1,
        "reason": "Không vi phạm quy tắc nào → mức 1 (VS)",
        "rule": "default_vs"
    }