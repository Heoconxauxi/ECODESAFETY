import pandas as pd
import json
import re
from pathlib import Path
from neo4j import Driver
import sys

# --- IMPORT FILE neo4j_connector ---
try:
    from neo4j_connector import get_neo4j_driver
except ImportError:
    print("Không thể import neo4j_connector.py")
    print("Đảm bảo file neo4j_connector.py nằm cùng thư mục hoặc trong PYTHONPATH")
    sys.exit(1)


# Xác định thư mục
try:
    SCRIPT_DIR = Path(__file__).resolve().parent
    ROOT_DIR = SCRIPT_DIR.parent
except:
    ROOT_DIR = Path.cwd().parent


SCHEMA_PATH = ROOT_DIR / "ontology" / "schema.json"
CSV_PATH = ROOT_DIR / "data" / "processed" / "ecodes_master.csv"

print(f"Script directory: {SCRIPT_DIR}")
print(f"Root directory: {ROOT_DIR}")
print(f"Schema path: {SCHEMA_PATH}")
print(f"CSV path: {CSV_PATH}")
print()

# --- Tải schema ---
try:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    print(f"Tải schema từ {SCHEMA_PATH}")
    print(f"   Classes: {schema.get('classes', [])}")
    print(f"   Relations: {schema.get('relations', [])}")
    print()
except Exception as e:
    print(f"Không thể đọc schema.json: {e}")
    sys.exit(1)


# --- Hàm chạy Cypher ---
def run_query(driver: Driver, query, params=None):
    """
    Chạy Cypher query với driver và parameters.
    """
    with driver.session() as session:
        result = session.run(query, params or {})
        return result


# --- Tạo constraints ---
def create_constraints(driver: Driver):
    """
    Tạo unique constraints cho các node theo schema.
    """
    print("Đang tạo constraints...")
    
    for c in schema.get("constraints", []):
        label = c.get("label")
        key = c.get("key")
        
        constraint_name = f"{label.lower()}_{key}_uniq"
        
        query = f"""
        CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
        FOR (n:{label}) REQUIRE n.{key} IS UNIQUE
        """
        
        try:
            run_query(driver, query)
            print(f"Created: {constraint_name}")
        except Exception as e:
            print(f"Warning for {constraint_name}: {e}")
    
    print("Constraints created.\n")


# --- Import data ---
def import_data(driver: Driver):
    """
    Import dữ liệu từ CSV vào Neo4j theo ontology đã định nghĩa.
    """
    # Đọc CSV
    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig").fillna("")
        print(f"Đã đọc {len(df)} dòng từ CSV.")
        print(f"Columns: {list(df.columns)}\n")
    except Exception as e:
        print(f"Lỗi khi đọc CSV: {e}")
        return

    print("🚀 Bắt đầu import dữ liệu...\n")
    
    success_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        try:
            ins = str(row["ins"]).strip()
            if not ins:
                continue

            name = str(row["name"]).strip()
            name_vn = str(row["name_vn"]).strip()
            adi = str(row["adi"]).strip()
            info = str(row["info"]).strip()

            # Tách function (support: "," "." mix)
            raw_functions = str(row["function"])
            functions = [
                f.strip()
                for f in re.split(r"[.,]", raw_functions)
                if f.strip()
            ]

            status_vn = str(row["status_vn"]).strip()
            level = str(row["level"]).strip()
            source = str(row["source"]).strip()

            # Cypher query để import một additive
            query = """
            MERGE (a:Additive {ins: $ins})
            SET a.name = $name,
                a.name_vn = $name_vn,
                a.adi = $adi,
                a.info = $info

            // --- FUNCTIONS ---
            WITH a, $functions AS funs
            UNWIND funs AS fname
                MERGE (f:Function {name: fname})
                MERGE (a)-[:HAS_FUNCTION]->(f)

            // --- STATUS ---
            WITH a WHERE $status_vn <> ""
            MERGE (st:Status {name: $status_vn})
            MERGE (a)-[:HAS_STATUS]->(st)

            // --- RISK LEVEL ---
            WITH a WHERE $level <> ""
            MERGE (r:RiskLevel {level: $level})
            MERGE (a)-[:HAS_RISK]->(r)

            // --- SOURCE ---
            WITH a WHERE $source <> ""
            MERGE (s:Source {name: $source})
            MERGE (a)-[:HAS_SOURCE]->(s)
            """

            run_query(
                driver,
                query,
                {
                    "ins": ins,
                    "name": name,
                    "name_vn": name_vn,
                    "adi": adi,
                    "info": info,
                    "functions": functions,
                    "status_vn": status_vn,
                    "level": level,
                    "source": source
                }
            )
            
            success_count += 1
            
            # Progress indicator
            if (idx + 1) % 10 == 0:
                print(f"   Processed {idx + 1}/{len(df)} rows...")

        except Exception as e:
            error_count += 1
            print(f"   ⚠️ Lỗi khi xử lý INS {ins}: {e}")

    print(f"\n✅ Import hoàn tất!")
    print(f"   - Success: {success_count}")
    print(f"   - Errors: {error_count}")
    print(f"   - Total: {len(df)}\n")


# --- Verify import ---
def verify_import(driver: Driver):
    """
    Kiểm tra kết quả import.
    """
    print("🔍 Đang verify dữ liệu...\n")
    
    queries = {
        "Additives": "MATCH (a:Additive) RETURN count(a) as count",
        "Functions": "MATCH (f:Function) RETURN count(f) as count",
        "Statuses": "MATCH (s:Status) RETURN count(s) as count",
        "RiskLevels": "MATCH (r:RiskLevel) RETURN count(r) as count",
        "Sources": "MATCH (s:Source) RETURN count(s) as count",
        "HAS_FUNCTION": "MATCH ()-[r:HAS_FUNCTION]->() RETURN count(r) as count",
        "HAS_STATUS": "MATCH ()-[r:HAS_STATUS]->() RETURN count(r) as count",
        "HAS_RISK": "MATCH ()-[r:HAS_RISK]->() RETURN count(r) as count",
        "HAS_SOURCE": "MATCH ()-[r:HAS_SOURCE]->() RETURN count(r) as count",
    }
    
    with driver.session() as session:
        for label, query in queries.items():
            result = session.run(query).single()
            count = result["count"]
            print(f"   {label:20s}: {count:5d}")
    
    print("\n✅ Verification complete.\n")


# --- MAIN ---
if __name__ == "__main__":
    print("=" * 60)
    print(" IMPORT DATASET TO NEO4J ".center(60, "="))
    print("=" * 60 + "\n")
    
    driver = None
    try:
        # Kết nối Neo4j
        driver = get_neo4j_driver()
        
        # Tạo constraints
        create_constraints(driver)
        
        # Import dữ liệu
        import_data(driver)
        
        # Verify kết quả
        verify_import(driver)
        
        print("=" * 60)
        print(" COMPLETED ".center(60, "="))
        print("=" * 60)
        
    except Exception as e:
        print(f"\nLỗi nghiêm trọng: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # ✅ Đóng driver đúng cách
        if driver:
            driver.close()
            print("\nĐã đóng kết nối Neo4j.")