from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "your_password_here"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

def get_facts_from_neo4j(ecode: str):
    """
    Truy vấn thông tin E-code từ Neo4j: Category, Effects, BannedIn, ADI, RiskLevel
    """
    with driver.session() as session:
        query = """
        MATCH (a:Additive {ECode:$ecode})
        OPTIONAL MATCH (a)-[:HAS_CATEGORY]->(cat:Category)
        OPTIONAL MATCH (a)-[:HAS_RISK]->(r:RiskLevel)
        OPTIONAL MATCH (a)-[:HAS_EFFECT]->(e:Effect)
        OPTIONAL MATCH (a)-[:BANNED_IN]->(c:Country)
        RETURN a.ECode AS ECode,
               a.CommonName AS CommonName,
               a.ADI_mgkg AS ADI_mgkg,
               cat.name AS Category,
               r.level AS RiskLevel,
               collect(DISTINCT e.name) AS Effects,
               collect(DISTINCT c.code) AS BannedIn
        """
        res = session.run(query, {"ecode": ecode}).data()
        if res:
            return res[0]
        return None
