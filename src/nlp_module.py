import re
import pandas as pd
from pathlib import Path

DATA_PATH = Path("../data/processed/ecodes_master.csv")

def extract_ecodes_from_text(text: str):
    """
    Trích xuất mã E-code từ văn bản OCR, ví dụ: "Contains E102, E211"
    """
    return re.findall(r'\bE\d{3,4}[A-Z]?\b', text.upper())

def normalize_additive_names(ecodes):
    """
    Chuẩn hóa tên phụ gia dựa vào ecodes_master.csv
    """
    df = pd.read_csv(DATA_PATH)
    df["ECode"] = df["ECode"].str.upper().str.strip()
    result = df[df["ECode"].isin(ecodes)][["ECode", "CommonName", "Category", "RiskLevel"]]
    return result.to_dict(orient="records")
