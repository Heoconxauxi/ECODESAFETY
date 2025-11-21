from src.ocr_module import extract_text_from_image
from src.nlp_module import extract_ecodes_from_text
from src.neo4j_connector import get_neo4j_driver, get_facts_from_neo4j, close_neo4j_driver
from src.rule_engine import evaluate_rules
import os
from typing import Dict, Any, List


def analyze_ecode(ecode_or_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Phân tích phụ gia theo INS/E-code.
    Trả về đầy đủ thông tin theo DATA MỚI + thêm:
        - level (true label)
        - rule_risk (dự đoán)
        - found = True/False
    """
    if context is None:
        context = {}

    source_text_used = ecode_or_text

    # OCR nếu là ảnh
    if os.path.exists(ecode_or_text) and ecode_or_text.lower().endswith(('.jpg', '.jpeg', '.png')):
        text = extract_text_from_image(ecode_or_text)
        source_text_used = text
    else:
        text = ecode_or_text.strip()

    # NLP trích INS/E-codes
    if not text.upper().startswith(("E", "INS")):
        ecodes = extract_ecodes_from_text(text)
    else:
        ecodes = [text]

    if not ecodes:
        return {
            "source_text": source_text_used,
            "analysis_results": [],
            "summary_warning": "Không tìm thấy mã phụ gia."
        }

    driver = get_neo4j_driver()
    results = []

    for code in ecodes:
        facts = get_facts_from_neo4j(driver, code)

        # -----------------------------
        # KHÔNG TÌM THẤY TRONG NEO4J
        # -----------------------------
        if not facts:
            results.append({
                "found": False,
                "ins": code,
                "message": "Không tìm thấy phụ gia trong cơ sở dữ liệu",
                "name": None,
                "name_vn": None,
                "function": [],
                "adi": None,
                "info": None,
                "status_vn": None,
                "level": None,            # TRUE LABEL
                "rule_risk": None,        # RULE
                "rule_reason": None,
                "rule_name": None
            })
            continue

        # -----------------------------
        # CÓ TRONG DATABASE → XỬ LÝ TIẾP
        # -----------------------------
        facts.update(context)
        decision = evaluate_rules(facts)

        results.append({
            "found": True,
            "ins": facts.get("ins"),
            "name": facts.get("name"),
            "name_vn": facts.get("name_vn"),
            "function": facts.get("function", []),
            "adi": facts.get("adi"),
            "info": facts.get("info"),
            "status_vn": facts.get("status_vn"),

            # TRUE LABEL từ dataset
            "level": facts.get("level"),

            # RULE ENGINE OUTPUT
            "rule_risk": decision.get("risk"),
            "rule_reason": decision.get("reason"),
            "rule_name": decision.get("rule"),
        })

    close_neo4j_driver()

    return {
        "source_text": source_text_used,
        "analysis_results": results
    }


def print_ecode_results(results):
    for res in results:
        print("\n====================================")

        if not res.get("found"):
            print(f"❌ Không tìm thấy phụ gia: {res['ins']}")
            continue

        print(f"🔹 INS/ECode       : {res['ins']}")
        print(f"   Tên EN          : {res['name']}")
        print(f"   Tên VN          : {res['name_vn']}")
        print(f"   Function        : {res['function']}")
        print(f"   ADI             : {res['adi']}")
        print(f"   Info            : {res['info']}")
        print(f"   Status VN (0/1) : {res['status_vn']}")

        print("\n--- So sánh Nhãn ---")
        print(f"   True Label      : {res['level']}")
        print(f"   Rule Predict    : {res['rule_risk']}")

        print("\n--- Rule Engine ---")
        print(f"   Lý do           : {res['rule_reason']}")
        print(f"   Rule áp dụng    : {res['rule_name']}")
    print("====================================\n")