from pathlib import Path
import yaml, re


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
    adi_has_limit = False   # chỉ để biết có “giới hạn số” hay không
    adi_display = None      # chuỗi dùng để hiển thị cho người dùng

    if raw_adi not in (None, "", "nan", "NaN", "updating"):
        adi_str = str(raw_adi).strip()

        # 1) Dạng số đơn: 3, 1.5, 0...
        try:
            float(adi_str)
            adi_has_limit = True
            adi_display = adi_str
        except ValueError:
            # 2) Dạng khoảng: 0-3, 0–3
            if re.match(r"^\d+(\.\d+)?\s*[-–]\s*\d+(\.\d+)?$", adi_str):
                adi_has_limit = True
                adi_display = adi_str

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
    if adi_display is not None:
        return {
            "risk": 2,
            "reason": f"ADI = {adi_display} mg/kg — cần giới hạn (SL)",
            "rule": "adi_numeric_safe_limit",
        }

    # -------------------------------------
    # 3) THIẾU THÔNG TIN — KHÔNG ĐƯỢC TRẢ VS
    # -------------------------------------
    if adi_display is None and status_vn is None:
        return {
            "risk": None,
            "reason": "Thiếu dữ liệu — không đủ thông tin để phân loại",
            "rule": "missing_data",
        }

    # -------------------------------------
    # 4) MỨC 1 — Rất an toàn (mặc định)
    # -------------------------------------
    return {
        "risk": 1,
        "reason": "Rất an toàn, không giới hạn (VS)",
        "rule": "default_vs",
    }

