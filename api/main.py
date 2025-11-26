from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
import tempfile, os
import jwt
import re

from src.analyze_ecode import analyze_ecode
from src.neo4j_connector import get_neo4j_driver, get_facts_from_neo4j

from api.info_generator import generate_additive_info
from api.auth import router as auth_router
from api.schemas import (
    AnalysisResult,
    AnalyzeTextInput,
    EcodeDetail,
    EcodeSearchItem,
    SearchResult,
    UserHistoryResponse,
    HistoryItem,
    HistoryAdditiveItem,
    AdditiveBase,
)

# ============================================================
# UTILS
# ============================================================

def normalize_query(q: Optional[str]) -> Optional[str]:
    """
    Chuẩn hóa query search:
    - Bỏ prefix 'E', 'INS', '-'
    - Đưa về lower-case
    """
    if not q:
        return q
    cleaned = re.sub(r"^(E|INS)\s*-?", "", q.strip(), flags=re.IGNORECASE)
    return cleaned.lower()


# ============================================================
# FASTAPI CONFIG
# ============================================================

app = FastAPI(
    title="EcodeSafety API",
    description="API phân tích phụ gia từ text hoặc ảnh.",
    version="5.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = "CHANGE_ME_SECRET"
JWT_ALG = "HS256"


# ============================================================
# USER CONTEXT + AUTH
# ============================================================

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
    """
    Ưu tiên lấy từ JWT (Authorization: Bearer <token>).
    Nếu không có, fallback từ X-Google-* header (dùng khi test/local).
    """
    # 1) JWT
    if authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise ValueError("Invalid auth scheme")

            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
            return UserContext(
                google_id=payload.get("sub"),
                email=payload.get("email"),
                name=payload.get("name"),
            )
        except Exception:
            # Cho front-end dùng ẩn danh nếu token hỏng
            return None

    # 2) Fallback header thô (khi dùng dev tools)
    if x_google_id:
        return UserContext(
            google_id=x_google_id,
            email=x_google_email,
            name=x_google_name,
        )

    return None


# ============================================================
# INCLUDE AUTH ROUTER
# ============================================================

app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ============================================================
# SAVE HISTORY
# ============================================================

def save_history_for_user(
    user: Optional[UserContext],
    source_text: str,
    analysis_results: List[dict],
):
    """
    Lưu lịch sử phân tích vào Neo4j:
      (u:User)-[:ANALYZED]->(h:History {at, ecodes, source_text})
    """
    if user is None:
        return

    ecodes = [res.get("ins") for res in analysis_results if res.get("ins")]
    if not ecodes:
        return

    driver = None
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (u:User {google_id: $gid})
                SET u.email = $email,
                    u.name  = $name

                CREATE (h:History {
                    at: datetime(),
                    ecodes: $ecodes,
                    source_text: $source_text
                })

                MERGE (u)-[:ANALYZED]->(h)
                """,
                {
                    "gid": user.google_id,
                    "email": user.email,
                    "name": user.name,
                    "ecodes": ecodes,
                    "source_text": source_text,
                },
            )
    except Exception as e:
        print("Lỗi khi lưu history:", e)
    finally:
        if driver:
            driver.close()


# ============================================================
# MAP ANALYSIS OUTPUT → SCHEMA (KHÔNG GỌI GEMINI)
# ============================================================

async def map_analysis_output_to_schema(analysis_output: dict) -> List[EcodeDetail]:
    """
    Phần này TRƯỚC ĐÂY có gọi Gemini cho từng phụ gia.
    Giờ đã bỏ hoàn toàn, chỉ map dữ liệu từ NLP/Neo4j → EcodeDetail,
    trường `info` để None. Info sẽ được gọi ở API /ecodes/info.
    """
    results = analysis_output.get("analysis_results", [])
    ecodes: List[EcodeDetail] = []

    for res in results:
        ins = res.get("ins")
        name = res.get("name")
        name_vn = res.get("name_vn")

        ecodes.append(
            EcodeDetail(
                found=res.get("found", True),
                ins=ins,
                name=name,
                name_vn=name_vn,
                functions=res.get("functions") or res.get("function") or [],
                adi=res.get("adi"),
                info=None,            # ❌ KHÔNG GỌI GEMINI Ở ĐÂY
                status_vn=res.get("status_vn"),
                level=res.get("level"),
                rule_risk=res.get("rule_risk"),
                rule_reason=res.get("rule_reason"),
                rule_name=res.get("rule_name"),
                message=res.get("message"),
                source=res.get("source"),
            )
        )
    return ecodes


# ============================================================
# ANALYZE TEXT
# ============================================================

@app.post("/ecode/analyze", response_model=AnalysisResult)
async def analyze_product_ingredients_text(
    input_data: AnalyzeTextInput,
    user: Optional[UserContext] = Depends(get_current_user),
):
    """
    Phân tích TEXT thành phần.
    - Gọi analyze_ecode (OCR+NLP+Neo4j)
    - map_analysis_output_to_schema (KHÔNG gọi Gemini)
    - Lưu history (User, History(ecodes, source_text))
    """
    try:
        source_text = input_data.input_text
        analysis_output = analyze_ecode(source_text)

        ecodes = await map_analysis_output_to_schema(analysis_output)

        # Lưu history: dùng dữ liệu raw từ ecodes
        save_history_for_user(user, source_text, [e.dict() for e in ecodes])

        return AnalysisResult(
            status="SUCCESS",
            ecodes_found=ecodes,
            message="OK",
        )
    except Exception as e:
        print("Lỗi /ecode/analyze:", e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ANALYZE IMAGE
# ============================================================

@app.post("/ecode/analyze_image", response_model=AnalysisResult)
async def analyze_product_image(
    image_file: UploadFile = File(...),
    user: Optional[UserContext] = Depends(get_current_user),
):
    """
    Phân tích ẢNH nhãn:
    - Lưu vào file tạm
    - Gọi analyze_ecode(path)
    - map_analysis_output_to_schema (KHÔNG gọi Gemini)
    - Lưu history
    """
    temp_file_path = None
    try:
        suffix = (
            f".{image_file.filename.split('.')[-1]}"
            if image_file.filename and "." in image_file.filename
            else ".jpg"
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            temp_file_path = tmp.name
            content = await image_file.read()
            tmp.write(content)

        analysis_output = analyze_ecode(temp_file_path)
        ecodes = await map_analysis_output_to_schema(analysis_output)

        source_text = analysis_output.get("raw_text", "")

        save_history_for_user(user, source_text, [e.dict() for e in ecodes])

        return AnalysisResult(
            status="SUCCESS",
            ecodes_found=ecodes,
            source_text=source_text,
            input_type="image",
            message="OK"
        )

    except Exception as e:
        print("Lỗi /ecode/analyze_image:", e)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


# ============================================================
# SEARCH ECODES (KHÔNG GỌI GEMINI)
# ============================================================

@app.get("/ecodes/search", response_model=SearchResult)
async def search_ecodes(
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    Search phụ gia theo:
      - INS
      - name
      - name_vn
    KHÔNG gọi Gemini, chỉ trả data từ Neo4j.
    """
    driver = None
    try:
        q_norm = normalize_query(q)

        driver = get_neo4j_driver()
        with driver.session() as session:

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
            WITH a, functions, risk_level AS risk_level, status_vn, sources
            ORDER BY a.ins
            SKIP $offset
            LIMIT $limit
            RETURN a.ins AS ins,
                   a.name AS name,
                   a.name_vn AS name_vn,
                   functions AS functions,
                   a.adi AS adi,
                   status_vn AS status_vn,
                   risk_level AS level,
                   sources[0] AS source
            """

            records = session.run(
                query, {"q": q_norm, "limit": limit, "offset": offset}
            )

            items: List[EcodeSearchItem] = []
            for r in records:
                items.append(
                    EcodeSearchItem(
                        ins=r["ins"],
                        name=r["name"],
                        name_vn=r["name_vn"],
                        functions=r["functions"],
                        adi=str(r["adi"]) if r["adi"] else None,
                        info=None,               # ❌ KHÔNG GỌI GEMINI Ở ĐÂY
                        status_vn=r["status_vn"],
                        level=r["level"],
                        source=r["source"],
                    )
                )

            # Đếm total (không có limit/offset)
            total_query = """
            MATCH (a:Additive)
            WHERE $q IS NULL
               OR $q = ""
               OR a.ins CONTAINS $q
               OR toLower(a.name) CONTAINS toLower($q)
               OR toLower(a.name_vn) CONTAINS toLower($q)
            RETURN count(a) AS total
            """

            total_record = session.run(total_query, {"q": q_norm}).single()
            total = total_record["total"] if total_record else 0

            return SearchResult(
                total=total,
                items=items,
            )

    except Exception as e:
        print("Lỗi /ecodes/search:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if driver:
            driver.close()

# ============================================
# LIST TẤT CẢ E-CODE (PHÂN TRANG)
# ============================================

@app.get("/ecodes/all", response_model=SearchResult)
async def list_all_ecodes(
    limit: int = 1000,   # bạn có thể tăng lên 500/1000 tuỳ DB
    offset: int = 0,
):
    driver = None
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
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

            records = session.run(query, {"limit": limit, "offset": offset})

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
            RETURN count(a) AS total
            """
            total = session.run(total_query).single()["total"]

        return SearchResult(
            query=None,       # vì đây là list all, không có q
            offset=offset,
            limit=limit,
            total=total,
            items=items,
        )
    finally:
        if driver:
            driver.close()

# ============================================================
# ECODES INFO – CHỈ GỌI GEMINI Ở ĐÂY
# ============================================================

class AdditiveInfoResponse(AdditiveBase):
    """
    Model trả về cho /ecodes/info
    Kế thừa AdditiveBase để tái sử dụng schema.
    """
    pass


@app.get("/ecodes/info", response_model=AdditiveInfoResponse)
async def get_additive_info(ins: str):
    """
    API lấy chi tiết 1 phụ gia:
      - Lấy data từ Neo4j
      - GỌI GEMINI 1 lần duy nhất sinh `info`
    Dùng cho trang chi tiết (additive_detail.html).
    """
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            record = session.run(
                """
                MATCH (a:Additive {ins: $ins})
                OPTIONAL MATCH (a)-[:HAS_FUNCTION]->(f:Function)
                OPTIONAL MATCH (a)-[:HAS_RISK]->(r:RiskLevel)
                OPTIONAL MATCH (a)-[:HAS_STATUS]->(s:Status)
                OPTIONAL MATCH (a)-[:HAS_SOURCE]->(src:Source)
                WITH a,
                     collect(DISTINCT f.name) AS functions,
                     r.level AS risk_level,
                     s.name AS status_vn,
                     collect(DISTINCT src.name) AS sources
                RETURN a.ins AS ins,
                       a.name AS name,
                       a.name_vn AS name_vn,
                       functions AS functions,
                       a.adi AS adi,
                       status_vn AS status_vn,
                       risk_level AS level,
                       sources[0] AS source
                """,
                {"ins": ins},
            ).single()

            if not record:
                raise HTTPException(status_code=404, detail=f"E-code {ins} không tồn tại")

            # GỌI GEMINI 1 LẦN
            ai_info = await generate_additive_info(
                record["ins"],
                record["name"],
                record["name_vn"],
            )

            return AdditiveInfoResponse(
                ins=record["ins"],
                name=record["name"],
                name_vn=record["name_vn"],
                functions=record["functions"],
                adi=str(record["adi"]) if record["adi"] else None,
                info=ai_info,
                status_vn=record["status_vn"],
                level=record["level"],
                # Các field rule_* để None (nếu cần có thể bổ sung sau)
                rule_risk=None,
                rule_reason=None,
                rule_name=None,
                found=True,
                message=None,
                source=record["source"],
            )

    except HTTPException:
        raise
    except Exception as e:
        print("Lỗi /ecodes/info:", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        driver.close()


# ============================================================
# USER HISTORY
# ============================================================

@app.get("/users/me/history", response_model=UserHistoryResponse)
async def get_my_history(
    user: UserContext = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """
    Đọc lịch sử phân tích của user:
      - Lấy (History) theo thời gian
      - Lấy lại facts từ Neo4j (get_facts_from_neo4j) cho từng history
      - KHÔNG gọi Gemini
    """
    if user is None:
        raise HTTPException(status_code=401, detail="User not logged in")

    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            records = session.run(
                """
                MATCH (u:User {google_id: $gid})-[:ANALYZED]->(h:History)
                RETURN h
                ORDER BY h.at DESC
                SKIP $offset
                LIMIT $limit
                """,
                {"gid": user.google_id, "offset": offset, "limit": limit},
            )

            items: List[HistoryItem] = []

            for r in records:
                h = r["h"]
                ecodes = h.get("ecodes", [])
                at = h.get("at")
                source_text = h.get("source_text")

                if isinstance(at, datetime):
                    analyzed_at = at
                else:
                    # fallback nếu at là string
                    analyzed_at = datetime.fromisoformat(str(at))

                # Lấy lại facts cho các E-code trong history
                facts = get_facts_from_neo4j(ecodes)

                additive_list: List[HistoryAdditiveItem] = []
                for a in facts:
                    additive_list.append(
                        HistoryAdditiveItem(
                            ins=a.get("ins"),
                            name=a.get("name"),
                            name_vn=a.get("name_vn"),
                            functions=a.get("functions") or [],
                            adi=a.get("adi"),
                            info=None,
                            status_vn=a.get("status_vn"),
                            level=a.get("level"),
                            rule_risk=a.get("rule_risk"),
                            rule_reason=a.get("rule_reason"),
                            rule_name=a.get("rule_name"),
                            message=a.get("message"),
                            source=a.get("source"),
                        )
                    )

                items.append(
                    HistoryItem(
                        ecodes=ecodes,
                        analyzed_at=analyzed_at,
                        source_text=source_text,
                        additives=additive_list,
                    )
                )

        return UserHistoryResponse(
            user_id=user.google_id,
            items=items,
        )

    finally:
        driver.close()
