from src.ocr_module import extract_text_from_image
from src.nlp_module import extract_ecodes_from_text
from src.neo4j_connector import get_neo4j_driver, get_facts_from_neo4j
from src.rule_engine import evaluate_rules
import os
from typing import Dict, Any


def analyze_ecode(ecode_or_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Phân tích phụ gia theo INS/E-code.
    """
    if context is None:
        context = {}

    source_text_used = ecode_or_text

    # =====================================
    # 1) OCR nếu là ảnh
    # =====================================
    if os.path.exists(ecode_or_text) and ecode_or_text.lower().endswith(('.jpg', '.jpeg', '.png')):
        text = extract_text_from_image(ecode_or_text)
        source_text_used = text
    else:
        text = ecode_or_text.strip()

    # =====================================
    # 2) NLP extract E-code
    # =====================================
    ecodes = extract_ecodes_from_text(text)

    if not ecodes:
        return {
            "source_text": source_text_used,
            "analysis_results": [],
            "summary_warning": "Không tìm thấy mã phụ gia."
        }

    # =====================================
    # 3) Query Neo4j bằng get_facts_from_neo4j()
    # =====================================
    driver = None
    results = []

    try:
        driver = get_neo4j_driver()

        for code in ecodes:
            facts = get_facts_from_neo4j(driver, code)

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
                    "level": None,
                    "rule_risk": None,
                    "rule_reason": None,
                    "rule_name": None
                })
                continue

            # merge thêm context
            facts.update(context)

            # rule engine
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
                "level": facts.get("level"),  # TRUE label Neo4j

                "rule_risk": decision.get("risk"),
                "rule_reason": decision.get("reason"),
                "rule_name": decision.get("rule"),
            })

    finally:
        if driver:
            driver.close()

    return {
        "source_text": source_text_used,
        "analysis_results": results
    }


def print_ecode_results(results):
    """
    In kết quả phân tích ra console một cách đẹp mắt.
    """
    for res in results:
        print("\n" + "="*50)

        if not res.get("found"):
            print(f"❌ Không tìm thấy phụ gia: {res['ins']}")
            print(f"   Message: {res.get('message')}")
            continue

        print(f"🔹 INS/E-code      : {res['ins']}")
        print(f"   Tên EN          : {res['name']}")
        print(f"   Tên VN          : {res['name_vn']}")
        print(f"   Chức năng       : {', '.join(res['function']) if res['function'] else 'N/A'}")
        print(f"   ADI             : {res['adi']}")
        print(f"   Thông tin       : {res['info'][:100] if res['info'] else 'N/A'}...")
        print(f"   Trạng thái VN   : {res['status_vn']}")

        print("\n--- So sánh Nhãn ---")
        print(f"   True Label      : {res['level']}")
        print(f"   Rule Prediction : {res['rule_risk']}")

        print("\n--- Rule Engine ---")
        print(f"   Lý do           : {res['rule_reason']}")
        print(f"   Rule áp dụng    : {res['rule_name']}")
    
    print("="*50 + "\n")


# =====================================
# TEST CODE
# =====================================
if __name__ == "__main__":
    print("🧪 Test analyze_ecode module\n")
    
    # Test case 1: Single E-code
    print("Test 1: Single E-code")
    result1 = analyze_ecode("Thành phần: E120, E162")
    print_ecode_results(result1["analysis_results"])
    
    # # Test case 2: Multiple E-codes in text
    # print("\nTest 2: Multiple E-codes")
    # result2 = analyze_ecode("Thành phần: E100, E330, E621")
    # print_ecode_results(result2["analysis_results"])
    
    # # Test case 3: Unknown E-code
    # print("\nTest 3: Unknown E-code")
    # result3 = analyze_ecode("E9999")
    # print_ecode_results(result3["analysis_results"])