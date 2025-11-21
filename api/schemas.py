from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class EcodeDetail(BaseModel):
    """
    Thông tin chi tiết một phụ gia trong kết quả phân tích.
    Gồm cả true label (level) và kết quả rule (rule_risk).
    """
    found: bool = Field(True, example=True)
    ins: str = Field(..., example="E100")
    name: Optional[str] = Field(None, example="Curcumin")
    name_vn: Optional[str] = Field(None, example="Tinh nghệ")
    function: List[str] = Field(default_factory=list, example=["Colorant"])
    adi: Optional[str] = Field(None, example="0-3 mg/kg bw/day")
    info: Optional[str] = None
    status_vn: Optional[int] = Field(None, example=0)

    # Nhãn thật trong data (true label: 1 / 2 / 4)
    level: Optional[int] = Field(None, example=2)

    # Kết quả từ Rule Engine
    rule_risk: Optional[int] = Field(None, example=4)
    rule_reason: Optional[str] = None
    rule_name: Optional[str] = None

    # Nếu không tìm thấy
    message: Optional[str] = Field(
        None, example="Không tìm thấy phụ gia trong cơ sở dữ liệu"
    )


class AnalysisResult(BaseModel):
    """
    Kết quả tổng hợp khi phân tích thành phần sản phẩm.
    """
    status: str = Field(..., example="SUCCESS")
    input_type: str = Field(..., example="TEXT_INPUT") 
    source_text: Optional[str] = Field(
        None, example="Thành phần: E100, E120"
    )
    ecodes_found: List[EcodeDetail] = Field(default_factory=list)


class AnalyzeTextInput(BaseModel):
    """Đầu vào khi phân tích bằng text."""
    input_text: str = Field(..., example="Thành phần: E100, E120")


class AnalyzeImageInput(BaseModel):
    """(Nếu sau này cần dùng meta ảnh)."""
    filename: str
    content_type: str


# ---------- SEARCH API ----------

class EcodeSearchItem(BaseModel):
    ins: str
    name: Optional[str] = None
    name_vn: Optional[str] = None
    function: List[str] = Field(default_factory=list)
    adi: Optional[str] = None
    info: Optional[str] = None
    status_vn: Optional[int] = None
    level: Optional[int] = None
    source: Optional[str] = None


class SearchResult(BaseModel):
    query: Optional[str] = None
    limit: int
    offset: int
    total: int
    items: List[EcodeSearchItem] = Field(default_factory=list)


# ---------- HISTORY API ----------

class HistoryItem(BaseModel):
    ins: str
    name: Optional[str] = None
    name_vn: Optional[str] = None
    analyzed_at: datetime
    source_text: Optional[str] = None
    true_level: Optional[int] = None
    rule_risk: Optional[int] = None


class UserHistoryResponse(BaseModel):
    user_id: str
    items: List[HistoryItem] = Field(default_factory=list)
