from pathlib import Path
import yaml

def evaluate_rules(facts, rules_path=None):
    """
    Áp dụng rule từ YAML vào dữ liệu fact của E-code.
    Tự động xác định đường dẫn tuyệt đối đến rules/risk_rules.yaml.
    """
    # ✅ Nếu không chỉ định, tự tìm file risk_rules.yaml trong thư mục gốc dự án
    if rules_path is None:
        rules_path = Path(__file__).resolve().parent.parent / "rules" / "risk_rules.yaml"

    with open(rules_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    for name in spec["priority"]:
        rule = spec["rules"][name]
        cond = rule.get("if", {})
        ok = True

        if "ecode_in" in cond:
            ok &= facts.get("ECode") in cond["ecode_in"]

        if "any_effect_in" in cond:
            ok &= any(
                e.lower() in [x.lower() for x in cond["any_effect_in"]]
                for e in facts.get("Effects", [])
            )

        if "banned_in_any_of" in cond:
            ok &= any(
                c.upper() in cond["banned_in_any_of"]
                for c in facts.get("BannedIn", [])
            )

        if "adi_mgkg_lt" in cond:
            adi = facts.get("ADI_mgkg")

            # Bỏ qua giá trị 'updating', 'NaN', '', None
            if isinstance(adi, str) and adi.strip().lower() in ("updating", "nan", ""):
                adi_val = None
            else:
                try:
                    adi_val = float(adi)
                except (TypeError, ValueError):
                    adi_val = None

            ok &= (adi_val is not None and adi_val < cond["adi_mgkg_lt"])


        if "context_daily_intake_mgkg_gt" in cond:
            intake = facts.get("intake_mgkg", 0)
            ok &= (intake > cond["context_daily_intake_mgkg_gt"])

        if "category_in" in cond:
            ok &= facts.get("Category") in cond["category_in"]

        if ok:
            return {
                "risk": rule["then"]["risk"],
                "reason": rule["then"]["reason"],
                "rule": name
            }

    return {
        "risk": "Safe",
        "reason": "Không vi phạm quy tắc nào",
        "rule": "default"
    }
