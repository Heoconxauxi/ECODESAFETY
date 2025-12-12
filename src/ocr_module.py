from __future__ import annotations
import logging
from typing import Optional, List
import unicodedata 
import re 

import cv2

try:
    import easyocr
except ImportError:
    easyocr = None


logger = logging.getLogger(__name__)
# Thiết lập logging cơ bản
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s")


class OCRBackendUnavailable(Exception):
    """Ngoại lệ tùy chỉnh khi backend OCR không khả dụng."""
    pass


class OCRPipeline:
    """
    Pipeline OCR sử dụng EasyOCR với các bước Tiền xử lý Ảnh (đơn giản)
    và Hậu xử lý Văn bản (chuẩn hóa Unicode) tối ưu cho ảnh chất lượng tốt.
    """
    def __init__(self, use_gpu: bool = False) -> None:
        self.use_gpu = use_gpu

        if easyocr:
            try:
                # Khởi tạo EasyOCR với ngôn ngữ Việt và Anh
                self.reader = easyocr.Reader(["vi", "en"], gpu=use_gpu)
                logger.info("EasyOCR loaded successfully (Languages: vi, en)")
            except Exception as e:
                self.reader = None
                logger.error(f"Failed to load EasyOCR: {e}")
        else:
            self.reader = None

        if not self.reader:
            raise OCRBackendUnavailable("EasyOCR is required but not available or failed to load.")

    # --- Hậu xử lý Văn bản ---
    
    def _normalize_vietnamese_unicode(self, text: str) -> str:
        """
        Chuẩn hóa Unicode tiếng Việt sang dạng Dựng sẵn (NFC).
        Giúp đảm bảo tính đồng nhất của văn bản cho mô-đun NLP.
        """
        return unicodedata.normalize("NFC", text)

    def _postprocess_text(self, text_list: List[str]) -> str:
        """
        Thực hiện ghép các dòng, chuẩn hóa Unicode và làm sạch văn bản cơ bản.
        """
        # 1. Ghép các dòng bằng dấu xuống dòng để giữ cấu trúc
        raw_text = "\n".join(text_list) 
        
        # 2. Chuẩn hóa Unicode
        normalized_text = self._normalize_vietnamese_unicode(raw_text)
        
        # 3. Làm sạch: Loại bỏ khoảng trắng thừa (nhiều dấu cách liền kề)
        cleaned_text = re.sub(r'\s+', ' ', normalized_text.strip())
        
        # 4. Thay thế dấu xuống dòng bằng dấu cách (tạo thành một chuỗi văn bản dài)
        return cleaned_text.replace('\n', ' ')

    # --- Tiền xử lý Ảnh và OCR ---
    
    def _preprocess_image(self, img):
        """
        Tiền xử lý ảnh đơn giản: Chỉ chuyển sang ảnh xám (Grayscale).
        """
        # Nếu ảnh đã rõ, việc chuyển sang Grayscale là đủ.
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray

    def ocr_region(self, img):
        """
        Thực hiện OCR trên một vùng ảnh đã được xử lý.
        Sử dụng mag_ratio để cải thiện nhận dạng văn bản nhỏ.
        """
        # Tiền xử lý ảnh (Chuyển sang xám)
        processed_img = self._preprocess_image(img)
        
        try:
            # Điều chỉnh mag_ratio (ví dụ: 1.5) để phóng to nội bộ và cải thiện nhận dạng chữ nhỏ.
            # Bạn nên thử nghiệm giữa 1.0 (mặc định), 1.5, và 2.0.
            result = self.reader.readtext(processed_img, 
                                          detail=0,
                                          mag_ratio=1.5) 
            
            if result:
                # Hậu xử lý văn bản
                final_text = self._postprocess_text(result)
                return final_text
        except Exception as e:
            logger.error(f"EasyOCR readtext failed: {e}")
            # Trả về chuỗi rỗng khi có lỗi
            return ""
        return ""

    def ocr_full_image(self, image_path: str) -> str:
        """Đọc và thực hiện OCR trên toàn bộ ảnh từ đường dẫn."""
        # Đọc ảnh. 
        img = cv2.imread(image_path) 
        
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        return self.ocr_region(img)


# --- Khởi tạo Pipeline Singleton ---

_PIPELINE: Optional[OCRPipeline] = None

def _get_pipeline() -> OCRPipeline:
    """Tạo hoặc trả về thể hiện (instance) duy nhất của OCRPipeline."""
    global _PIPELINE
    if _PIPELINE is None:
        # Tắt GPU (use_gpu=False) để đảm bảo tính di động, có thể bật nếu cần
        try:
            _PIPELINE = OCRPipeline(use_gpu=False)
        except OCRBackendUnavailable as e:
            logger.error(e)
            raise # Báo lỗi ra ngoài nếu OCR không khả dụng
    return _PIPELINE


# --- Hàm Chính (Public API) ---

def extract_text_from_image(image_path: str) -> str:
    """Hàm chính được UI gọi – OCR full ảnh và trả về văn bản đã xử lý."""
    try:
        pipeline = _get_pipeline()
        return pipeline.ocr_full_image(image_path)
    except Exception as e:
        logger.error(f"Fatal error during text extraction: {e}")
        return "" # Trả về chuỗi rỗng nếu có lỗi nghiêm trọng