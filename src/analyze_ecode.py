from src.ocr_module import extract_text_from_image
from src.nlp_module import extract_ecodes_from_text
from src.neo4j_connector import get_neo4j_driver
from src.rule_engine import evaluate_rules
import os
from typing import Dict, Any, List


def get_additive_info(driver, ins_code: str) -> Dict[str, Any]:
    """
    Wrapper function để query additive từ Neo4j.
    Tương thích với cả tên cũ (get_facts_from_neo4j) và mới.
    """
    try:
        with driver.session() as session:
            query = """
            MATCH (a:Additive {ins: $ins})
            OPTIONAL MATCH (a)-[:HAS_FUNCTION]->(f:Function)
            OPTIONAL MATCH (a)-[:HAS_STATUS]->(s:Status)
            OPTIONAL MATCH (a)-[:HAS_RISK]->(r:RiskLevel)
            OPTIONAL MATCH (a)-[:HAS_SOURCE]->(src:Source)
            RETURN a.ins AS ins,
                   a.name AS name,
                   a.name_vn AS name_vn,
                   a.adi AS adi,
                   a.info AS info,
                   collect(DISTINCT f.name) AS functions,
                   s.name AS status_vn,
                   r.level AS level,
                   collect(DISTINCT src.name) AS sources
            """
            result = session.run(query, {"ins": ins_code}).data()
            
            if result:
                data = result[0]
                return {
                    "ins": data["ins"],
                    "name": data["name"],
                    "name_vn": data["name_vn"],
                    "adi": data["adi"],
                    "info": data["info"],
                    "function": data["functions"],
                    "status_vn": data["status_vn"],
                    "level": data["level"],
                    "sources": data["sources"]
                }
            return None
    except Exception as e:
        print(f"Lỗi khi query additive {ins_code}: {e}")
        return None


def analyze_ecode(ecode_or_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Phân tích phụ gia theo INS/E-code.
    
    Args:
        ecode_or_text: Có thể là:
            - Đường dẫn file ảnh (.jpg, .jpeg, .png) → OCR
            - Text chứa INS/E-code → NLP extract
            - INS code trực tiếp (E100, INS100)
        context: Thông tin thêm (user profile, preferences, etc.)
    
    Returns:
        Dict chứa:
            - source_text: Text đã xử lý
            - analysis_results: List các phụ gia đã phân tích
            - summary_warning: Cảnh báo tổng quan (nếu có)
    """
    if context is None:
        context = {}

    source_text_used = ecode_or_text

    # =====================================
    # BƯỚC 1: OCR NẾU LÀ ẢNH
    # =====================================
    if os.path.exists(ecode_or_text) and ecode_or_text.lower().endswith(('.jpg', '.jpeg', '.png')):
        text = extract_text_from_image(ecode_or_text)
        source_text_used = text
    else:
        text = ecode_or_text.strip()

    # =====================================
    # BƯỚC 2: TRÍCH XUẤT INS/E-CODES
    # =====================================
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

    # =====================================
    # BƯỚC 3: TẠO CONNECTION & PHÂN TÍCH
    # =====================================
    driver = None
    results = []

    try:
        driver = get_neo4j_driver()

        for code in ecodes:
            facts = get_additive_info(driver, code)

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
                    "rule_risk": None,        # RULE PREDICTION
                    "rule_reason": None,
                    "rule_name": None
                })
                continue

            # -----------------------------
            # CÓ TRONG DATABASE → XỬ LÝ TIẾP
            # -----------------------------
            # Merge context vào facts để rule engine có thể sử dụng
            facts.update(context)
            
            # Chạy rule engine
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

    finally:
        # ✅ LUÔN ĐÓNG DRIVER
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
    result1 = analyze_ecode("E100")
    print_ecode_results(result1["analysis_results"])
    
    # Test case 2: Multiple E-codes in text
    print("\nTest 2: Multiple E-codes")
    result2 = analyze_ecode("Thành phần: E100, E330, E621")
    print_ecode_results(result2["analysis_results"])
    
    # Test case 3: Unknown E-code
    print("\nTest 3: Unknown E-code")
    result3 = analyze_ecode("E9999")
    print_ecode_results(result3["analysis_results"])