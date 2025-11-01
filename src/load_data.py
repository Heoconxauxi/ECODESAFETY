"""
Script: load_data.py (đặt trong thư mục src/)
Tự động tạo cấu trúc Ontology và nạp dữ liệu CSV vào Neo4j.
Sử dụng file kết nối 'neo4j_connector.py'
"""

import pandas as pd
import json
from pathlib import Path
from neo4j import Driver
import sys

# --- 1. IMPORT TỪ FILE SIBLING (ngang hàng) ---
# Vì file này nằm trong 'src/', nó có thể import trực tiếp
try:
    from neo4j_connector import get_neo4j_driver, close_neo4j_driver
except ImportError:
    print("Lỗi: Không thể import 'neo4j_connector'.")
    print("Đảm bảo file này và 'neo4j_connector.py' cùng nằm trong thư mục 'src/'.")
    sys.exit()

# --- 2. Cấu hình PATH ---
# Xác định thư mục gốc (EcodeSafety/)
try:
    SCRIPT_DIR = Path(__file__).resolve().parent # -> .../EcodeSafety/src
    ROOT_DIR = SCRIPT_DIR.parent               # -> .../EcodeSafety/
except NameError:
    # Fallback nếu chạy trong môi trường tương tác (notebook)
    ROOT_DIR = Path.cwd().parent 
    print(f"Cảnh báo: Không thể dùng __file__, giả định ROOT_DIR là {ROOT_DIR}")


SCHEMA_PATH = ROOT_DIR / "ontology" / "schema.json"
CSV_PATH = ROOT_DIR / "data" / "ecodes_master.csv"

# --- Tải schema ---
try:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    print(f"✅ Tải schema từ {SCHEMA_PATH} thành công.")
except Exception as e:
    print(f"❌ Lỗi: Không thể đọc file schema tại {SCHEMA_PATH}. Lỗi: {e}")
    sys.exit()

# --- Hàm thực thi Cypher (nhận driver làm tham số) ---
def run_query(driver: Driver, query, params=None):
    with driver.session() as session:
        session.run(query, params or {})

# --- 3. Tạo Constraints (nhận driver làm tham số) ---
def create_constraints(driver: Driver):
    print("🔄 Bắt đầu tạo constraints...")
    for c in schema["constraints"]:
        q = f"""
        CREATE CONSTRAINT {c['label'].lower()}_{c['key']}_uniq IF NOT EXISTS
        FOR (n:{c['label']}) REQUIRE n.{c['key']} IS UNIQUE
        """
        run_query(driver, q)
    print("✅ Constraints đã được tạo (hoặc đã tồn tại).")

# --- 4. Nạp dữ liệu (nhận driver làm tham số) ---
def import_data(driver: Driver):
    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig").fillna("")
        print(f"📦 Đã đọc {len(df)} dòng từ {CSV_PATH}.")
    except FileNotFoundError:
        print(f"❌ Lỗi: Không tìm thấy file CSV tại {CSV_PATH}.")
        return
    except Exception as e:
        print(f"❌ Lỗi khi đọc file CSV: {e}")
        return

    print("🔄 Bắt đầu nạp dữ liệu vào Neo4j (việc này có thể mất vài phút)...")
    
    for _, row in df.iterrows():
        try:
            ecode = row["ECode"].strip()
            if not ecode:
                continue

            # Đọc tất cả các cột
            common = row["CommonName"].strip()
            cat = row["Category"].strip()
            adi = row["ADI_mgkg"].strip()
            risk = row["RiskLevel"].strip().capitalize()
            contra = row["Contraindications"].strip()
            source = row["Source"].strip()
            effects = [e.strip() for e in str(row["Effects"]).split(",") if e.strip()]
            countries = [c.strip().upper() for c in str(row["BannedIn"]).split(",") if c.strip()]

            # Query tối ưu (chỉ tạo node/quan hệ nếu có dữ liệu)
            query = """
            MERGE (a:Additive {ECode: $ecode})
            SET a.CommonName = $common, a.ADI_mgkg = $adi, a.Contraindications = $contra
            WITH a WHERE $cat <> ""
            MERGE (cat:Category {name: $cat})
            MERGE (a)-[:HAS_CATEGORY]->(cat)
            WITH a WHERE $risk <> ""
            MERGE (r:RiskLevel {level: $risk})
            MERGE (a)-[:HAS_RISK]->(r)
            WITH a WHERE $source <> ""
            MERGE (s:Source {name: $source})
            MERGE (a)-[:HAS_SOURCE]->(s)
            WITH a
            UNWIND $effects AS eff
                MERGE (e:Effect {name: eff})
                MERGE (a)-[:HAS_EFFECT]->(e)
            WITH a
            UNWIND $countries AS co
                MERGE (c:Country {code: co})
                MERGE (a)-[:BBANNED_IN]->(c)
            """
            
            run_query(driver, query, {
                "ecode": ecode, "common": common, "cat": cat,
                "adi": adi, "risk": risk, "contra": contra,
                "source": source, "effects": effects, "countries": countries
            })
        except Exception as e:
            print(f"⚠️ Lỗi khi xử lý dòng {ecode}: {e}")

    print("✅ Nạp dữ liệu hoàn tất.")


if __name__ == "__main__":
    main_driver = None
    try:
        # 1. LẤY KẾT NỐI (từ file neo4j_connector)
        main_driver = get_neo4j_driver()
        print("========================================")
        
        # 2. Chạy logic
        create_constraints(main_driver)
        import_data(main_driver)
        
        print("========================================")
        print("🎯 Ontology và dữ liệu đã được nạp thành công.")

    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng xảy ra: {e}")
    finally:
        # 3. LUÔN LUÔN ĐÓNG KẾT NỐI
        close_neo4j_driver()