from src.ocr_module import extract_text_from_image
from src.nlp_module import extract_ecodes_from_text
from src.neo4j_connector import get_neo4j_driver, get_facts_from_neo4j, close_neo4j_driver
from src.rule_engine import evaluate_rules
import os
from typing import Dict, Any, List

def analyze_ecode(ecode_or_text: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Phân tích E-code hoặc văn bản có chứa E-code.
    Trả về Dict chứa source_text (kết quả OCR/text gốc) và List[Dict] phân tích.
    """
    if context is None:
        context = {}
    
    source_text_used = ecode_or_text # Lưu trữ đầu vào/kết quả OCR để trả về

    # 1. Xử lý OCR nếu là file ảnh
    if os.path.exists(ecode_or_text) and ecode_or_text.lower().endswith(('.jpg', '.jpeg', '.png')):
        print("Đang trích xuất văn bản từ ảnh bằng OCR...")
        ocr_text = extract_text_from_image(ecode_or_text)
        source_text_used = ocr_text # Cập nhật source_text là kết quả OCR
        
        # Nếu OCR không thành công, trả về kết quả lỗi sớm
        if not ocr_text:
            return {
                "source_text": "Lỗi: Không trích xuất được văn bản từ ảnh.",
                "analysis_results": [],
                "summary_warning": "LỖI: Không trích xuất được văn bản từ ảnh."
            }
        
        print("Văn bản OCR thu được:\n", source_text_used)
        text_for_nlp = ocr_text

    else:
        # Nếu không phải ảnh, đây là text đầu vào
        text_for_nlp = ecode_or_text.strip()
        source_text_used = text_for_nlp

    # 2. Xử lý NLP/Direct E-code
    if not text_for_nlp.upper().startswith("E"):
        # Là đoạn văn -> trích E-code bằng NLP
        ecodes: List[str] = extract_ecodes_from_text(text_for_nlp)
    else:
        # Là mã E-code trực tiếp
        ecodes = [text_for_nlp]

    if not ecodes:
        print("\nKhông phát hiện được E-code nào.")
        return {
            "source_text": source_text_used,
            "analysis_results": [],
            "summary_warning": "Không tìm thấy E-code nào trong thành phần."
        }
    
    print("\nCác E-code trích xuất được:", ", ".join(ecodes))
    
    # 3. Truy vấn Knowledge Graph và Rule Engine
    driver = get_neo4j_driver()
    results: List[Dict[str, Any]] = []
    
    for ecode in ecodes:
        facts = get_facts_from_neo4j(driver, ecode)
        
        if not facts:
            results.append({
                "ECode": ecode,
                "CommonName": "Không rõ",
                "Category": "N/A",
                "RiskLevel": "N/A", # Thêm các field cần thiết để mapping Pydantic không lỗi
                "risk": "Unknown",
                "reason": "Không tìm thấy trong cơ sở dữ liệu"
            })
            continue

        facts.update(context)
        decision = evaluate_rules(facts)
        facts.update(decision)
        results.append(facts)

    close_neo4j_driver()

    # Trả về kết quả tổng hợp cho API
    return {
        "source_text": source_text_used,
        "analysis_results": results,
    }

def print_ecode_results(results):
    """
    Hiển thị kết quả phân tích E-code dưới dạng dễ đọc.
    """
    for res in results:
        print("\n==============================")
        print(f"🔹 Mã phụ gia (ECode): {res.get('ECode', 'N/A')}")
        if 'CommonName' in res:
            print(f"   Tên thông dụng   : {res.get('CommonName', 'N/A')}")
        if 'Category' in res:
            print(f"   Nhóm phụ gia     : {res.get('Category', 'N/A')}")
        if 'RiskLevel' in res:
            print(f"   Cấp độ rủi ro DB : {res.get('RiskLevel', 'N/A')}")
        print(f"   ➤ Đánh giá Rule  : {res.get('risk', 'N/A')}")
        print(f"   ➤ Lý do          : {res.get('reason', 'N/A')}")
        if 'rule' in res:
            print(f"   (Theo rule: {res.get('rule', 'N/A')})")
    print("==============================\n")


# --- TEST ---
if __name__ == "__main__":
    output = analyze_ecode("E120")
    print_ecode_results(output["analysis_results"])

