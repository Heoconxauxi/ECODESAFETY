from pathlib import Path
import yaml


def evaluate_rules(facts, rules_path=None):
    """
    RuleEngine 3 mức:
      - 4: Cấm/Độc hại (status_vn = 1)
      - 2: An toàn có giới hạn (ADI dạng số 0–n)
      - 1: Rất an toàn (mặc định)
    """

    # status_vn
    status_vn = facts.get("status_vn")
    try:
        status_vn = int(status_vn)
    except:
        status_vn = None

    # ADI
    raw_adi = facts.get("adi")
    if raw_adi in (None, "", "nan", "NaN", "updating"):
        adi_val = None
    else:
        try:
            adi_val = float(raw_adi)
        except:
            adi_val = None

    # -------------------------------------
    # 1) MỨC 4 — Cấm/Độc hại
    # -------------------------------------
    if status_vn == 1:
        return {
            "risk": 4,
            "reason": "Không được phép tại Việt Nam (BT)",
            "rule": "status_not_allowed_vn",
        }

    # -------------------------------------
    # 2) MỨC 2 — An toàn có giới hạn
    # -------------------------------------
    if adi_val is not None:
        return {
            "risk": 2,
            "reason": f"ADI = {adi_val} mg/kg — cần giới hạn (SL)",
            "rule": "adi_numeric_safe_limit",
        }

    # -------------------------------------
    # 3) MỨC 1 — Rất an toàn (mặc định)
    # -------------------------------------
    return {
        "risk": 1,
        "reason": "Rất an toàn, không giới hạn (VS)",
        "rule": "default_vs",
    }
