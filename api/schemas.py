from pydantic import BaseModel, Field
from typing import List, Optional

class EcodeAnalysis(BaseModel):
    """Mô tả dữ liệu của một E-code đã phân tích."""
    ecode: str = Field(..., example="E330")
    name_vn: str = Field(..., example="Acid Citric")
    category: Optional[str] = Field(None, example="Chất điều chỉnh độ acid")
    safety_level: Optional[str] = Field(None, example="AN_TOÀN")
    warnings: Optional[List[str]] = Field(default_factory=list, example=["Không có rủi ro nghiêm trọng."])

class AnalysisResult(BaseModel):
    """Kết quả tổng hợp khi phân tích thành phần sản phẩm."""
    status: str = Field(..., example="SUCCESS")
    input_type: str = Field(..., example="TEXT_INPUT") 
    source_text: Optional[str] = Field(None, example="Thành phần: E330, E211")
    ecodes_found: List[EcodeAnalysis] = Field(default_factory=list)
    # Nếu sau này bạn cần thêm trường mới, chỉ cần thêm vào đây:
    # processing_time: Optional[float] = None
    # detected_language: Optional[str] = None

class AnalyzeTextInput(BaseModel):
    """Đầu vào khi phân tích bằng text."""
    input_text: str = Field(..., example="Thành phần: E330, E211")

class AnalyzeImageInput(BaseModel):
    """Đầu vào khi phân tích bằng hình ảnh."""
    filename: str
    content_type: str
