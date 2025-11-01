# file: src/neo4j_connector.py
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError
from typing import Dict, Any, Optional

# --- 1. Quản lý kết nối (Driver Management) ---

# Tải biến môi trường (file .env) từ thư mục gốc của dự án
load_dotenv() 

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD")

# Biến global (private) để lưu trữ driver instance (Singleton)
_driver: Optional[Driver] = None

def get_neo4j_driver() -> Driver:
    """
    Khởi tạo và trả về một instance Driver (Singleton).
    Tái sử dụng instance nếu nó đã được tạo.
    """
    global _driver
    if _driver is None:
        print("Đang tạo kết nối Neo4j mới...")
        if not NEO4J_URI or not NEO4J_USER or not NEO4J_PASS:
            raise EnvironmentError("Thiếu thông tin kết nối NEO4J trong file .env")
        try:
            # Tạo driver
            _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
            # Kiểm tra kết nối
            _driver.verify_connectivity()
            print("Kết nối Neo4j thành công!")
        except (ServiceUnavailable, AuthError) as e:
            print(f"Lỗi: Không thể kết nối tới Neo4j tại {NEO4J_URI}. Chi tiết: {e}")
            _driver = None # Đảm bảo _driver vẫn là None nếu thất bại
            raise # Ném lỗi ra ngoài để ứng dụng chính biết và dừng lại
    
    return _driver

def close_neo4j_driver():
    """
    Đóng kết nối driver nếu nó đã được khởi tạo.
    Gọi hàm này khi ứng dụng của bạn tắt.
    """
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
        print("Đã đóng kết nối Neo4j.")

# --- 2. Xử lý truy vấn (Query Handling) ---

# def get_facts_from_neo4j(driver: Driver, ecode: str) -> Optional[Dict[str, Any]]:
#     """
#     Truy vấn thông tin E-code từ Neo4j: Category, Effects, BannedIn, ADI, RiskLevel
#     (Đây chính là hàm bạn đã cung cấp, được điều chỉnh để nhận 'driver' làm tham số)
#     """
#     if not driver:
#         print("Lỗi: Neo4j driver chưa được khởi tạo.")
#         return None
            
#     try:
#         # Sử dụng session từ driver đã cung cấp
#         with driver.session() as session:
#             query = """
#             MATCH (a:Additive {ECode:$ecode})
#             OPTIONAL MATCH (a)-[:HAS_CATEGORY]->(cat:Category)
#             OPTIONAL MATCH (a)-[:HAS_RISK]->(r:RiskLevel)
#             OPTIONAL MATCH (a)-[:HAS_EFFECT]->(e:Effect)
#             OPTIONAL MATCH (a)-[:BANNED_IN]->(c:Country)
#             RETURN a.ECode AS ECode,
#                    a.CommonName AS CommonName,
#                    a.ADI_mgkg AS ADI_mgkg,
#                    cat.name AS Category,
#                    r.level AS RiskLevel,
#                    collect(DISTINCT e.name) AS Effects,
#                    collect(DISTINCT c.code) AS BannedIn
#             """
#             # Chạy truy vấn và lấy dữ liệu
#             res = session.run(query, {"ecode": ecode}).data()
            
#             if res:
#                 return res[0] # Trả về bản ghi đầu tiên (và duy nhất)
#             return None # Không tìm thấy E-code
            
#     except ServiceUnavailable as e:
#         print(f"Lỗi dịch vụ Neo4j khi truy vấn {ecode}: {e}")
#         return None
#     except Exception as e:
#         print(f"Lỗi không xác định khi truy vấn {ecode}: {e}")
#         return None

# # --- 3. Block để chạy thử nghiệm (Test) file này ---
# # Bạn có thể chạy file này trực tiếp bằng: python src/neo4j_connector.py

# if __name__ == "__main__":
#     print("--- Chạy thử nghiệm neo4j_connector.py ---")
#     main_driver = None
#     try:
#         # 1. Lấy kết nối
#         main_driver = get_neo4j_driver()
        
#         # 2. Thử truy vấn một E-code (Hãy thay đổi E-code bạn muốn test)
#         ecode_test = "E100" 
#         print(f"Đang truy vấn thông tin cho: {ecode_test}")
        
#         facts = get_facts_from_neo4j(main_driver, ecode_test)
        
#         if facts:
#             import json
#             print("Kết quả truy vấn thành công:")
#             # In ra kết quả dạng JSON cho dễ đọc
#             print(json.dumps(facts, indent=2, ensure_ascii=False))
#         else:
#             print(f"Không tìm thấy dữ liệu cho {ecode_test}.")

#     except Exception as e:
#         print(f"Lỗi trong quá trình chạy thử: {e}")
#     finally:
#         # 3. Luôn đóng kết nối
#         close_neo4j_driver()