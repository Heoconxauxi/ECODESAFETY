"""
============================================================
E-CODE SAFETY - RULE-BASED EVALUATION (evaluate_rules + sklearn)
============================================================
"""

import pandas as pd
from pathlib import Path
from src.rule_engine import evaluate_rules
from sklearn.metrics import classification_report, confusion_matrix


# --------------------------------------------------------
# CONFIG
# --------------------------------------------------------
ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "processed" / "ecodes_master.csv"

print("📌 Đang đọc dữ liệu từ:", CSV_PATH)


# --------------------------------------------------------
# LOAD CSV
# --------------------------------------------------------
df = pd.read_csv(CSV_PATH, dtype=str)

# Fix missing level
missing = df["level"].isna().sum()
if missing > 0:
    print(f"⚠ Có {missing} dòng thiếu level → gán -1")
    df["level"] = df["level"].fillna("-1")

df["level"] = df["level"].astype(int)

# Chỉ lấy dữ liệu có label hợp lệ
eval_df = df[df["level"] != -1].copy()
print(f"✔ Tổng mẫu hợp lệ để đánh giá: {len(eval_df)}")


# --------------------------------------------------------
# APPLY RULE ENGINE
# --------------------------------------------------------
def apply_rule(row):
    """
    Evaluate rule for each row
    Facts must use lowercase keys:
      adi → facts["adi"]
      status_vn → facts["status_vn"]
    """
    data = {
        "adi": row.get("adi"),                 # <-- viết thường
        "status_vn": row.get("status_vn"),     # <-- viết thường
    }

    result = evaluate_rules(data)
    return result.get("risk", None)


print("🔄 Đang chạy Rule Engine...")
eval_df["rule_pred"] = eval_df.apply(apply_rule, axis=1)
print("✔ Rule Engine hoàn tất!\n")


# --------------------------------------------------------
# EVALUATION (SCIKIT-LEARN)
# --------------------------------------------------------
y_true = eval_df["level"].tolist()
y_pred = eval_df["rule_pred"].tolist()

print("====================================================")
print("📊 BÁO CÁO ĐÁNH GIÁ (SCIKIT-LEARN)")
print("====================================================")

print(classification_report(y_true, y_pred, digits=3))

print("\n🧩 Confusion Matrix:")
print(confusion_matrix(y_true, y_pred))


# --------------------------------------------------------
# EXPORT ERROR CASES
# --------------------------------------------------------
errors = eval_df[eval_df["level"] != eval_df["rule_pred"]]

print("\n====================================================")
print("❌ CÁC MẪU LỖI (RULE ≠ LABEL)")
print("====================================================")
print(errors[["ins", "name", "adi", "status_vn", "level", "rule_pred"]].head(20))

error_path = ROOT / "rulebase_errors.csv"
errors.to_csv(error_path, index=False, encoding="utf-8")

print(f"\n📁 Xuất lỗi tại: {error_path}")
print("\n🎉 ĐÁNH GIÁ HOÀN TẤT!")
