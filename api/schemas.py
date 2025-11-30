from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# ============================================================
# MODEL CHUNG CHO MỌI TRƯỜNG HỢP
# ============================================================

class AdditiveBase(BaseModel):
    """
    Model phụ gia thống nhất dùng cho mọi API.
    Trường `info` sẽ được sinh ra bằng API Chat (LLM).
    """

    # Thông tin cơ bản
    ins: str = Field(..., example="E100")
    name: Optional[str] = Field(None, example="Curcumin")
    name_vn: Optional[str] = Field(None, example="Tinh nghệ")

    # functions/function được hợp nhất thành 1
    functions: List[str] = Field(default_factory=list, example=["Colorant"])

    # ADI và status
    adi: Optional[str] = Field(None, example="0–3 mg/kg bw/day")
    status_vn: Optional[int] = Field(None, example=1)

    # Nhãn thật
    level: Optional[int] = Field(None, example=2)

    # Rule engine output
    rule_risk: Optional[int] = None
    rule_reason: Optional[str] = None
    rule_name: Optional[str] = None

    # Metadata
    found: Optional[bool] = Field(None)
    message: Optional[str] = None

    # Source từ DB (EFSA, JECFA,...)
    source: Optional[str] = None

    # ⭐  NEW: field này dự định sẽ được LLM sinh ra
    info: Optional[str] = Field(
        None,
        example="Curcumin là chất tạo màu vàng chiết xuất từ củ nghệ..."
    )


# ============================================================
# ANALYSIS API
# ============================================================

class EcodeDetail(AdditiveBase):
    """Alias cho API phân tích."""
    pass


class AnalysisResult(BaseModel):
    input_type: Optional[str] = None
    source_text: Optional[str] = None
    ecodes_found: List[EcodeDetail] = []


class AnalyzeTextInput(BaseModel):
    input_text: str


class AnalyzeImageInput(BaseModel):
    filename: str
    content_type: str


# ============================================================
# SEARCH API
# ============================================================

class EcodeSearchItem(AdditiveBase):
    pass


class SearchResult(BaseModel):
    query: Optional[str]
    limit: int
    offset: int
    total: int
    items: List[EcodeSearchItem] = Field(default_factory=list)


# ============================================================
# HISTORY API
# ============================================================

class HistoryAdditiveItem(AdditiveBase):
    pass


class HistoryItem(BaseModel):
    ecodes: List[str]
    analyzed_at: datetime
    source_text: Optional[str]
    additives: List[HistoryAdditiveItem] = Field(default_factory=list)
    input_type: Optional[str] = "text"
    source_image_b64: Optional[str] = None


class UserHistoryResponse(BaseModel):
    user_id: str
    items: List[HistoryItem] = Field(default_factory=list)
