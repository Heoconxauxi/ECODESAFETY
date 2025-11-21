# file: src/neo4j_connector.py
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError
from typing import Dict, Any, Optional

# Tải biến môi trường (file .env) từ thư mục gốc của dự án
load_dotenv() 

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD")

def get_neo4j_driver() -> Driver:
    """
    Tạo và trả về một instance Driver MỚI mỗi lần gọi.
    Người gọi có TRÁCH NHIỆM đóng driver sau khi sử dụng.
    
    Usage:
        driver = get_neo4j_driver()
        try:
            with driver.session() as session:
                # ... your queries ...
        finally:
            driver.close()
    """
    print("Đang tạo kết nối Neo4j mới...")
    
    if not NEO4J_URI or not NEO4J_USER or not NEO4J_PASS:
        raise EnvironmentError("Thiếu thông tin kết nối NEO4J trong file .env")
    
    try:
        # Tạo driver mới
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        
        # Kiểm tra kết nối
        driver.verify_connectivity()
        print("Kết nối Neo4j thành công!")
        
        return driver
        
    except (ServiceUnavailable, AuthError) as e:
        print(f"Lỗi: Không thể kết nối tới Neo4j tại {NEO4J_URI}. Chi tiết: {e}")
        raise


def get_facts_from_neo4j(driver: Driver, ins_code: str) -> Optional[Dict[str, Any]]:
    """
    Truy vấn thông tin Additive từ Neo4j theo schema mới:
    - Additive properties: ins, name, name_vn, adi, info
    - Relations: HAS_FUNCTION, HAS_STATUS, HAS_RISK, HAS_SOURCE
    
    Args:
        driver: Neo4j driver instance
        ins_code: INS code (ví dụ: "E100", "E621")
    
    Returns:
        Dict chứa thông tin additive hoặc None nếu không tìm thấy
    """
    if not driver:
        print("Lỗi: Neo4j driver chưa được khởi tạo.")
        return None
            
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
            res = session.run(query, {"ins": ins_code}).data()
            
            if res:
                data = res[0]
                # Chuyển đổi format để dễ sử dụng
                return {
                    "ins": data["ins"],
                    "name": data["name"],
                    "name_vn": data["name_vn"],
                    "adi": data["adi"],
                    "info": data["info"],
                    "function": data["functions"],  # List of function names
                    "status_vn": data["status_vn"],
                    "level": data["level"],  # Risk level: "1", "2", "3"
                    "sources": data["sources"]  # List of source names
                }
            return None
            
    except ServiceUnavailable as e:
        print(f"Lỗi dịch vụ Neo4j khi truy vấn {ins_code}: {e}")
        return None
    except Exception as e:
        print(f"Lỗi không xác định khi truy vấn {ins_code}: {e}")
        return None


# Test code
if __name__ == "__main__":
    print("--- Chạy thử nghiệm neo4j_connector.py ---")
    driver = None
    try:
        # 1. Lấy kết nối
        driver = get_neo4j_driver()
        
        # 2. Thử truy vấn một INS code
        test_codes = ["100(i)", "621", "330"]
        
        for ins_code in test_codes:
            print(f"\n{'='*50}")
            print(f"Đang truy vấn thông tin cho: {ins_code}")
            print('='*50)
            
            facts = get_facts_from_neo4j(driver, ins_code)
            
            if facts:
                import json
                print("✅ Kết quả truy vấn thành công:")
                print(json.dumps(facts, indent=2, ensure_ascii=False))
            else:
                print(f"❌ Không tìm thấy dữ liệu cho {ins_code}.")

    except Exception as e:
        print(f"❌ Lỗi trong quá trình chạy thử: {e}")
    finally:
        # 3. Luôn đóng kết nối
        if driver:
            driver.close()
            print("\n✅ Đã đóng kết nối Neo4j.")