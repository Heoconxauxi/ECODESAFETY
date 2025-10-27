from nlp_module import extract_ecodes_from_text
from neo4j_connector import get_facts_from_neo4j
from rule_engine import evaluate_rules

def analyze_ecode(ecode_or_text: str, context=None):
    """
    Phân tích E-code hoặc văn bản có chứa E-code
    """
    if context is None:
        context = {}

    # Nếu nhập cả đoạn văn bản → trích E-code
    if not ecode_or_text.strip().upper().startswith("E"):
        ecodes = extract_ecodes_from_text(ecode_or_text)
    else:
        ecodes = [ecode_or_text.strip().upper()]

    results = []
    for ecode in ecodes:
        facts = get_facts_from_neo4j(ecode)
        if not facts:
            results.append({"ECode": ecode, "risk": "Unknown", "reason": "Không tìm thấy trong cơ sở dữ liệu"})
            continue

        facts.update(context)
        decision = evaluate_rules(facts)
        facts.update(decision)
        results.append(facts)
    return results
