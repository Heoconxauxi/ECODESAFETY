import pandas as pd
import json
import re
from pathlib import Path
from neo4j import Driver
import sys

# --- IMPORT FILE neo4j_connector ---
try:
    from neo4j_connector import get_neo4j_driver, close_neo4j_driver
except ImportError:
    print("Không thể import neo4j_connector.py")
    sys.exit()


# Xác định thư mục
try:
    SCRIPT_DIR = Path(__file__).resolve().parent
    ROOT_DIR = SCRIPT_DIR.parent
except:
    ROOT_DIR = Path.cwd().parent


SCHEMA_PATH = ROOT_DIR / "ontology" / "schema.json"
CSV_PATH = ROOT_DIR / "data" / "processed" / "ecodes_master.csv"

# --- Tải schema ---
try:
    schema_text = SCHEMA_PATH.read_text(encoding="utf-8")
    schema = json.loads(schema_text)
    print(f"Tải schema từ {SCHEMA_PATH}")
except Exception as e:
    print(f"Không thể đọc schema.json: {e}")
    sys.exit()


# --- Hàm chạy Cypher ---
def run_query(driver: Driver, query, params=None):
    with driver.session() as session:
        session.run(query, params or {})


# --- Tạo constraints ---
def create_constraints(driver: Driver):
    print("Tạo constraints...")
    for c in schema["constraints"]:
        q = f"""
        CREATE CONSTRAINT {c['label'].lower()}_{c['key']}_uniq IF NOT EXISTS
        FOR (n:{c['label']}) REQUIRE n.{c['key']} IS UNIQUE
        """
        run_query(driver, q)
    print("✅ DONE.")


# --- Import data ---
def import_data(driver: Driver):
    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig").fillna("")
        print(f"📦 Đã đọc {len(df)} dòng.")
    except Exception as e:
        print(f"Lỗi khi đọc CSV: {e}")
        return

    print("Bắt đầu import dữ liệu...")

    for _, row in df.iterrows():
        try:
            ins = str(row["ins"]).strip()
            if not ins:
                continue

            name = row["name"].strip()
            name_vn = row["name_vn"].strip()
            adi = row["adi"].strip()
            info = row["info"].strip()

            # Tách function (support: "," "." mix)
            raw_functions = str(row["function"])
            functions = [
                f.strip()
                for f in re.split(r"[.,]", raw_functions)
                if f.strip()
            ]

            status_vn = row["status_vn"].strip()
            level = row["level"].strip().lower()
            source = row["source"].strip()

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

        except Exception as e:
            print(f"⚠️ Lỗi khi xử lý INS {ins}: {e}")

    print("🎉 Import dữ liệu hoàn tất.")


# --- MAIN ---
if __name__ == "__main__":
    main_driver = None
    try:
        main_driver = get_neo4j_driver()
        print("==============================")
        create_constraints(main_driver)
        import_data(main_driver)
        print("==============================")
        print("Hoàn thành import dataset.")
    except Exception as e:
        print(f"Lỗi nghiêm trọng: {e}")
    finally:
        if main_driver:
            close_neo4j_driver()
