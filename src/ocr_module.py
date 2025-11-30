from __future__ import annotations
import logging
from typing import Optional

import cv2

try:
    import easyocr
except ImportError:
    easyocr = None


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s")


class OCRBackendUnavailable(Exception):
    pass


class OCRPipeline:
    def __init__(self, use_gpu: bool = False) -> None:
        self.use_gpu = use_gpu

        if easyocr:
            try:
                self.reader = easyocr.Reader(["vi", "en"], gpu=use_gpu)
                logger.info("EasyOCR loaded successfully")
            except Exception:
                self.reader = None
        else:
            self.reader = None

        if not self.reader:
            raise OCRBackendUnavailable("EasyOCR is required but not available")

    def ocr_region(self, img):
        """OCR trực tiếp ảnh gốc – không preprocess."""
        try:
            result = self.reader.readtext(img, detail=0)
            if result:
                return " ".join(result).strip()
        except Exception:
            pass
        return ""

    def ocr_full_image(self, image_path: str) -> str:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        return self.ocr_region(img)


_PIPELINE: Optional[OCRPipeline] = None


def _get_pipeline() -> OCRPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = OCRPipeline(use_gpu=False)
    return _PIPELINE


def extract_text_from_image(image_path: str) -> str:
    """Hàm chính được UI gọi – OCR full ảnh."""
    pipeline = _get_pipeline()

    try:
        return pipeline.ocr_full_image(image_path)
    except Exception:
        return ""
