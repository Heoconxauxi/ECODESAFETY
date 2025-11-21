from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import tempfile, os
import jwt

from src.analyze_ecode import analyze_ecode
from src.neo4j_connector import get_neo4j_driver
from api.auth import router as auth_router
from api.schemas import (
    AnalysisResult,
    AnalyzeTextInput,
    EcodeDetail,
    EcodeSearchItem,
    SearchResult,
    UserHistoryResponse,
    HistoryItem,
)

# ============================================
# CONFIG APP
# ============================================

app = FastAPI(
    title="EcodeSafety API",
    description="API phân tích phụ gia (INS/E-code) từ Text hoặc Ảnh, có search và lịch sử người dùng.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# AUTH CONFIG
# ============================================

JWT_SECRET = "CHANGE_ME_SECRET"
JWT_ALG = "HS256"

GOOGLE_CLIENT_ID = "249383931866-a7m46i32lsoagdvs5u0pdp0sgd86ha9m.apps.googleusercontent.com"


# ============================================
# USER CONTEXT
# ============================================

class UserContext:
    def __init__(self, google_id: str, email: Optional[str], name: Optional[str]):
        self.google_id = google_id
        self.email = email
        self.name = name


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_google_id: Optional[str] = Header(None, alias="X-Google-Id"),
    x_google_email: Optional[str] = Header(None, alias="X-Google-Email"),
    x_google_name: Optional[str] = Header(None, alias="X-Google-Name"),
) -> Optional[UserContext]:

    # 1️⃣ Ưu tiên JWT từ Authorization
    if authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() == "bearer":
                payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
                return UserContext(
                    google_id=payload.get("sub"),
                    email=payload.get("email"),
                    name=payload.get("name"),
                )
        except Exception:
            pass

    # 2️⃣ Dùng X-Google-* (test mode)
    if x_google_id:
        return UserContext(
            google_id=x_google_id,
            email=x_google_email,
            name=x_google_name,
        )

    return None


# ============================================
# INCLUDE AUTH ROUTER (GOOGLE LOGIN)
# ============================================

app.include_router(auth_router)


# ============================================
# SAVE HISTORY
# ============================================

def save_history_for_user(
    user: Optional[UserContext],
    source_text: str,
    analysis_results: List[dict],
):
    if user is None:
        return

    driver = None
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            for res in analysis_results:
                if not res.get("found"):
                    continue

                ins = res.get("ins")
                if not ins:
                    continue

                session.run(
                    """
                    MERGE (u:User {google_id: $gid})
                    SET u.email = $email,
                        u.name = $name

                    MERGE (a:Additive {ins: $ins})

                    MERGE (u)-[r:ANALYZED]->(a)
                    SET r.at = datetime(),
                        r.source_text = $source_text,
                        r.true_level = $true_level,
                        r.rule_risk = $rule_risk
                    """,
                    {
                        "gid": user.google_id,
                        "email": user.email,
                        "name": user.name,
                        "ins": ins,
                        "source_text": source_text,
                        "true_level": res.get("level"),
                        "rule_risk": res.get("rule_risk"),
                    },
                )
    finally:
        if driver:
            driver.close()


# ============================================
# MAPPING OUTPUT
# ============================================

def map_analysis_output_to_schema(analysis_output: dict) -> List[EcodeDetail]:
    results = analysis_output.get("analysis_results", [])
    ecodes: List[EcodeDetail] = []

    for res in results:
        ecodes.append(
            EcodeDetail(
                found=res.get("found", True),
                ins=res.get("ins"),
                name=res.get("name"),
                name_vn=res.get("name_vn"),
                function=res.get("function", []),
                adi=str(res.get("adi")) if res.get("adi") is not None else None,
                info=res.get("info"),
                status_vn=res.get("status_vn"),
                level=res.get("level"),
                rule_risk=res.get("rule_risk"),
                rule_reason=res.get("rule_reason"),
                rule_name=res.get("rule_name"),
                message=res.get("message"),
            )
        )
    return ecodes


# ============================================
# ANALYZE TEXT
# ============================================

@app.post("/ecode/analyze", response_model=AnalysisResult)
async def analyze_product_ingredients_text(
    input_data: AnalyzeTextInput,
    user: Optional[UserContext] = Depends(get_current_user),
):
    try:
        source_text = input_data.input_text
        analysis_output = analyze_ecode(source_text)
        ecodes = map_analysis_output_to_schema(analysis_output)

        save_history_for_user(user, source_text, [e.dict() for e in ecodes])

        return AnalysisResult(
            status="SUCCESS",
            input_type="TEXT_INPUT",
            source_text=analysis_output.get("source_text", source_text),
            ecodes_found=ecodes,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ANALYZE IMAGE
# ============================================

@app.post("/ecode/analyze_image", response_model=AnalysisResult)
async def analyze_product_image(
    image_file: UploadFile = File(...),
    user: Optional[UserContext] = Depends(get_current_user),
):
    temp_file_path = None
    try:
        suffix = (
            f".{image_file.filename.split('.')[-1]}"
            if "." in image_file.filename
            else ".tmp"
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await image_file.read())
            temp_file_path = tmp.name

        analysis_output = analyze_ecode(temp_file_path)
        ecodes = map_analysis_output_to_schema(analysis_output)

        save_history_for_user(
            user,
            analysis_output.get("source_text", "OCR"),
            [e.dict() for e in ecodes],
        )

        return AnalysisResult(
            status="SUCCESS",
            input_type="IMAGE_INPUT",
            source_text=analysis_output.get("source_text", "OCR Failed"),
            ecodes_found=ecodes,
        )

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


# ============================================
# SEARCH API
# ============================================

@app.get("/ecodes/search", response_model=SearchResult)
async def search_ecodes(
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    driver = None
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            # ✅ Query phù hợp với schema: Additive-[:HAS_FUNCTION]->Function
            query = """
            MATCH (a:Additive)
            OPTIONAL MATCH (a)-[:HAS_FUNCTION]->(f:Function)
            OPTIONAL MATCH (a)-[:HAS_RISK]->(r:RiskLevel)
            OPTIONAL MATCH (a)-[:HAS_STATUS]->(s:Status)
            OPTIONAL MATCH (a)-[:HAS_SOURCE]->(src:Source)
            WITH a, 
                 collect(DISTINCT f.name) AS functions,
                 r.level AS risk_level,
                 s.name AS status_vn,
                 collect(DISTINCT src.name) AS sources
            WHERE $q IS NULL
               OR $q = ""
               OR a.ins CONTAINS $q
               OR toLower(a.name) CONTAINS toLower($q)
               OR toLower(a.name_vn) CONTAINS toLower($q)
            WITH a, functions, risk_level, status_vn, sources
            ORDER BY a.ins
            SKIP $offset
            LIMIT $limit
            RETURN a.ins AS ins,
                   a.name AS name,
                   a.name_vn AS name_vn,
                   functions AS functions,
                   a.adi AS adi,
                   a.info AS info,
                   status_vn AS status_vn,
                   risk_level AS level,
                   sources[0] AS source
        """

            records = session.run(query, {"q": q, "limit": limit, "offset": offset})

            items = []
            for r in records:
                items.append(
                    EcodeSearchItem(
                        ins=r["ins"],
                        name=r["name"],
                        name_vn=r["name_vn"],
                        function=r["functions"],
                        adi=str(r["adi"]) if r["adi"] else None,
                        info=r["info"],
                        status_vn=r["status_vn"],
                        level=r["level"],
                        source=r["source"],
                    )
                )

            total_query = """
            MATCH (a:Additive)
            WHERE $q IS NULL
               OR $q = ""
               OR a.ins CONTAINS $q
               OR toLower(a.name) CONTAINS toLower($q)
               OR toLower(a.name_vn) CONTAINS toLower($q)
            RETURN count(a) AS total
            """

            total = session.run(total_query, {"q": q}).single()["total"]

        return SearchResult(
            query=q,
            offset=offset,
            limit=limit,
            total=total,
            items=items,
        )
    finally:
        if driver:
            driver.close()


# ============================================
# HISTORY API
# ============================================

@app.get("/users/me/history", response_model=UserHistoryResponse)
async def get_my_history(
    user: UserContext = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):

    if user is None:
        raise HTTPException(status_code=401, detail="User not logged in")

    driver = None
    try:
        driver = get_neo4j_driver()
        
        with driver.session() as session:
            records = session.run(
                """
                MATCH (u:User {google_id: $gid})-[r:ANALYZED]->(a:Additive)
                RETURN a.ins AS ins,
                       a.name AS name,
                       a.name_vn AS name_vn,
                       r.at AS at,
                       r.source_text AS source_text,
                       r.true_level AS true_level,
                       r.rule_risk AS rule_risk
                ORDER BY r.at DESC
                SKIP $offset
                LIMIT $limit
                """,
                {"gid": user.google_id, "limit": limit, "offset": offset},
            )

            items = []
            for r in records:
                at = r["at"]
                if hasattr(at, "to_native"):
                    at = at.to_native()

                items.append(
                    HistoryItem(
                        ins=r["ins"],
                        name=r["name"],
                        name_vn=r["name_vn"],
                        analyzed_at=at,
                        source_text=r["source_text"],
                        true_level=r["true_level"],
                        rule_risk=r["rule_risk"],
                    )
                )

        return UserHistoryResponse(
            user_id=user.google_id,
            items=items,
        )
    finally:
        if driver:
            driver.close()