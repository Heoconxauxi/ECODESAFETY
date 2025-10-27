"""
Script: load_ontology_from_schema.py
Tự động tạo cấu trúc Ontology và nạp dữ liệu CSV vào Neo4j.
"""

from neo4j import GraphDatabase
import pandas as pd
import json
from pathlib import Path

# --- Cấu hình ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "your_password_here"  # 🔒 đổi lại bằng mật khẩu thật của bạn

SCHEMA_PATH = Path("../ontology/schema.json")
CSV_PATH = Path("../data/processed/ecodes_master.csv")

# --- Kết nối Neo4j ---
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# --- Tải schema ---
schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

# --- Hàm thực thi Cypher ---
def run_query(query, params=None):
    with driver.session() as session:
        session.run(query, params or {})

# --- 1️⃣ Tạo Constraints ---
def create_constraints():
    for c in schema["constraints"]:
        q = f"""
        CREATE CONSTRAINT {c['label'].lower()}_{c['key']}_uniq IF NOT EXISTS
        FOR (n:{c['label']}) REQUIRE n.{c['key']} IS UNIQUE
        """
        run_query(q)
    print("✅ Constraints created.")

# --- 2️⃣ Nạp dữ liệu từ CSV ---
def import_data():
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig").fillna("")
    print(f"📦 Importing {len(df)} rows...")

    for _, row in df.iterrows():
        ecode = row["ECode"].strip()
        common = row["CommonName"].strip()
        cat = row["Category"].strip()
        adi = row["ADI_mgkg"]
        risk = row["RiskLevel"].strip().capitalize()
        effects = [e.strip() for e in str(row["Effects"]).split(",") if e.strip()]
        countries = [c.strip().upper() for c in str(row["BannedIn"]).split(",") if c.strip()]

        query = """
        MERGE (a:Additive {ECode: $ecode})
        SET a.CommonName = $common, a.ADI_mgkg = $adi
        MERGE (cat:Category {name: $cat})
        MERGE (a)-[:HAS_CATEGORY]->(cat)
        MERGE (r:RiskLevel {level: $risk})
        MERGE (a)-[:HAS_RISK]->(r)
        WITH a
        UNWIND $effects AS eff
            MERGE (e:Effect {name: eff})
            MERGE (a)-[:HAS_EFFECT]->(e)
        WITH a
        UNWIND $countries AS co
            MERGE (c:Country {code: co})
            MERGE (a)-[:BANNED_IN]->(c)
        """
        run_query(query, {
            "ecode": ecode,
            "common": common,
            "cat": cat,
            "adi": float(adi) if adi != "" else None,
            "risk": risk if risk else "Unknown",
            "effects": effects,
            "countries": countries
        })

    print("✅ Data import completed.")


if __name__ == "__main__":
    create_constraints()
    import_data()
    driver.close()
    print("🎯 Ontology and data successfully loaded into Neo4j.")
