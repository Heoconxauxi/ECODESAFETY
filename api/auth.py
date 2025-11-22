from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt, time

from src.neo4j_connector import get_neo4j_driver

router = APIRouter()

GOOGLE_CLIENT_ID = "249383931866-a7m46i32lsoagdvs5u0pdp0sgd86ha9m.apps.googleusercontent.com"
JWT_SECRET = "CHANGE_ME_SECRET"
JWT_EXPIRE_SECONDS = 60 * 60 * 24 * 7  # 7 ngày


class GoogleLoginRequest(BaseModel):
    id_token: str


@router.post("/google-login")
def google_login(payload: GoogleLoginRequest):
    driver = None
    try:
        # 1. LOG TOKEN
        print("Received ID Token:", payload.id_token)

        # 2. VERIFY ID TOKEN
        idinfo = id_token.verify_oauth2_token(
            payload.id_token,
            requests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=30  # Cho phép chênh lệch 30 giây
        )
        
        print("Token Verified Successfully:", idinfo.get("email"))

        google_id = idinfo["sub"]
        email = idinfo.get("email")
        name = idinfo.get("name")

        # 3. SAVE USER IN NEO4J
        driver = get_neo4j_driver()
        with driver.session() as session:
            session.run(
                """
                MERGE (u:User {google_id: $gid})
                SET u.email = $email,
                    u.name = $name
                """,
                {"gid": google_id, "email": email, "name": name},
            )

        jwt_payload = {
            "sub": google_id,
            "email": email,
            "name": name,
            "exp": time.time() + JWT_EXPIRE_SECONDS
        }
        token = jwt.encode(jwt_payload, JWT_SECRET, algorithm="HS256")

        return {
            "access_token": token,
            "user": {
                "google_id": google_id,
                "email": email,
                "name": name
            }
        }

    except Exception as e:
        print(f"LỖI XÁC THỰC GOOGLE ID TOKEN CHI TIẾT: {e}")
        raise HTTPException(status_code=401, detail="Invalid ID Token")
    
    finally:
        if driver:
            driver.close()