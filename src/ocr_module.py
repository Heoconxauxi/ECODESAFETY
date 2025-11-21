"""
ocr_module.py

Module OCR tổng quát cho đồ án EcodeSafety:
- Kết hợp PaddleOCR (PPOCR), EasyOCR, Tesseract theo kiểu ensemble
- Tự động dò vùng 'Thành phần' / 'Ingredients' trên nhãn sản phẩm
- Crop block thành phần và OCR lại cho sạch
- Public API: extract_text_from_image(image_path: str)  (GIỮ NGUYÊN TÊN)

Yêu cầu cài đặt:
    pip install paddlepaddle paddleocr easyocr pytesseract opencv-python
"""

from __future__ import annotations

import os
import logging
from typing import List, Tuple, Optional, Dict, Any

import cv2
import numpy as np

# ---------- Logging ----------
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
    )

# ---------- Optional imports ----------

try:
    from paddleocr import PaddleOCR  # type: ignore
except ImportError:
    PaddleOCR = None  # type: ignore
    logger.warning("PaddleOCR chưa được cài. Sẽ fallback sang EasyOCR/Tesseract.")

try:
    import easyocr  # type: ignore
except ImportError:
    easyocr = None  # type: ignore
    logger.warning("EasyOCR chưa được cài. Sẽ chỉ dùng PaddleOCR/Tesseract.")

import pytesseract  # Tesseract bắt buộc (nhưng nếu chưa cài, sẽ báo lỗi khi dùng)


# ---------- Kiểu dữ liệu ----------

BBox = List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]


class OCRBackendUnavailable(Exception):
    """Ném ra khi không có backend OCR nào dùng được."""
    pass


# ---------- Class Pipeline ----------

class OCRPipeline:
    """
    Pipeline OCR tổng:
    - Ưu tiên dùng PaddleOCR để detect + nhận dạng
    - Kết hợp EasyOCR + Tesseract để ensemble
    """

    def __init__(self, use_gpu: bool = False) -> None:
        # Lưu flag, hiện tại Python 3.13 nên thực chất vẫn dùng CPU,
        # nhưng giữ nguyên tham số cho tương lai bạn đổi môi trường.
        self.use_gpu = use_gpu

        self.ppocr: Optional[Any] = None
        self.easy_reader: Optional[Any] = None

        # ---- PaddleOCR ----
        if PaddleOCR is not None:
            try:
                # LƯU Ý: KHÔNG dùng use_gpu, device, det_db_score_mode
                # vì version PaddleOCR hiện tại của bạn không hỗ trợ.
                self.ppocr = PaddleOCR(
                    lang="vi",
                    use_textline_orientation=True,  # theo cảnh báo deprecation
                    show_log=False,
                )
                logger.info("Khởi tạo PaddleOCR thành công.")
            except Exception as e:
                logger.error(f"Lỗi khởi tạo PaddleOCR: {e}")
                self.ppocr = None

        # ---- EasyOCR ----
        if easyocr is not None:
            try:
                # gpu=use_gpu: nếu PyTorch là CPU build, nó sẽ tự fallback CPU.
                self.easy_reader = easyocr.Reader(
                    ["vi", "en"],
                    gpu=use_gpu
                )
                logger.info("Khởi tạo EasyOCR thành công.")
            except Exception as e:
                logger.error(f"Lỗi khởi tạo EasyOCR: {e}")
                self.easy_reader = None

        if self.ppocr is None and self.easy_reader is None:
            logger.warning(
                "Không khởi tạo được PaddleOCR lẫn EasyOCR. "
                "Pipeline sẽ chỉ dùng Tesseract (kém chính xác hơn)."
            )

    # -----------------------------
    # 1. Hàm DETECT: trả về list box + text thô
    # -----------------------------
    def detect_boxes_with_text(
        self, img: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        Trả về list dict:
        {
            "bbox": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
            "text": "string",
            "conf": float
        }
        """

        boxes: List[Dict[str, Any]] = []

        # Ưu tiên PaddleOCR
        if self.ppocr is not None:
            try:
                result = self.ppocr.ocr(img, cls=True)
                # result: list[list[line]]
                for line_group in result:
                    for line in line_group:
                        bbox = line[0]         # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                        txt = line[1][0]       # text
                        conf = float(line[1][1])
                        boxes.append({"bbox": bbox, "text": txt, "conf": conf})
                return boxes
            except Exception as e:
                logger.error(f"Lỗi detect bằng PaddleOCR: {e}")

        # Fallback: EasyOCR (vừa detect vừa nhận dạng)
        if self.easy_reader is not None:
            try:
                result = self.easy_reader.readtext(img)  # [ [bbox,text,conf], ... ]
                for (bbox, txt, conf) in result:
                    boxes.append(
                        {"bbox": bbox, "text": txt, "conf": float(conf)}
                    )
                return boxes
            except Exception as e:
                logger.error(f"Lỗi detect bằng EasyOCR: {e}")

        # Fallback cuối: Tesseract (detection yếu)
        logger.warning("Detect bằng Tesseract - ít chính xác hơn.")
        data = pytesseract.image_to_data(
            img, lang="eng+vie", output_type=pytesseract.Output.DICT
        )
        n = len(data["text"])
        for i in range(n):
            txt = data["text"][i]
            conf = float(data["conf"][i])
            if conf <= 0 or not txt.strip():
                continue
            x = data["left"][i]
            y = data["top"][i]
            w = data["width"][i]
            h = data["height"][i]
            bbox = [
                [x, y],
                [x + w, y],
                [x + w, y + h],
                [x, y + h],
            ]
            boxes.append({"bbox": bbox, "text": txt, "conf": conf})

        return boxes

    # -----------------------------
    # 2. Hàm ENSEMBLE OCR cho 1 region (crop)
    # -----------------------------
    def ocr_region_ensemble(self, roi: np.ndarray) -> str:
        """
        OCR 1 vùng ảnh nhỏ (ROI) bằng 3 backend:
        - PaddleOCR
        - EasyOCR
        - Tesseract

        Sau đó hợp nhất text theo luật voting / ưu tiên.
        """
        candidates: List[str] = []

        # PaddleOCR
        if self.ppocr is not None:
            try:
                res = self.ppocr.ocr(roi, cls=True)
                texts = []
                for line_group in res:
                    for line in line_group:
                        texts.append(line[1][0])
                pp_text = " ".join(texts).strip()
                if pp_text:
                    candidates.append(pp_text)
            except Exception as e:
                logger.debug(f"PaddleOCR roi error: {e}")

        # EasyOCR
        if self.easy_reader is not None:
            try:
                res = self.easy_reader.readtext(roi, detail=0)
                if isinstance(res, list) and len(res) > 0:
                    ez_text = " ".join(res).strip()
                    if ez_text:
                        candidates.append(ez_text)
            except Exception as e:
                logger.debug(f"EasyOCR roi error: {e}")

        # Tesseract
        try:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        except Exception:
            gray = roi
        try:
            tess_text = pytesseract.image_to_string(
                gray, lang="eng+vie", config="--psm 6"
            ).strip()
            if tess_text:
                candidates.append(tess_text)
        except Exception as e:
            logger.debug(f"Tesseract roi error: {e}")

        if not candidates:
            return ""

        return self._vote_text(candidates)

    @staticmethod
    def _vote_text(candidates: List[str]) -> str:
        """
        Voting đơn giản:
        - Nếu có 2 chuỗi giống nhau → chọn
        - Nếu tất cả khác nhau → chọn chuỗi dài nhất (thường là đầy đủ nhất)
        """
        # Normalize
        norm = [c.strip() for c in candidates if c.strip()]
        if not norm:
            return ""

        # Nếu có chuỗi trùng nhau >= 2 lần
        for c in norm:
            if norm.count(c) >= 2:
                return c

        # Nếu hoàn toàn khác nhau, chọn chuỗi dài nhất
        return max(norm, key=len)

    # -----------------------------
    # 3. Tìm vùng "Thành phần / Ingredients"
    # -----------------------------
    def find_ingredient_region(
        self, img: np.ndarray
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Tìm bounding box (left, top, right, bottom) cho block thành phần.

        Logic:
        - OCR toàn ảnh → lấy list boxes (bbox + text)
        - Tìm box chứa 'thành phần' / 'ingredients' / 'composition'
        - Lấy tất cả box nằm phía dưới → gộp thành 1 bounding box lớn
        """
        h, w = img.shape[:2]
        boxes = self.detect_boxes_with_text(img)

        if not boxes:
            logger.warning("Không phát hiện được text nào trên ảnh.")
            return None

        KEYWORDS = [
            "thành phần",
            "thanh phan",
            "thành phẩn",
            "ingredients",
            "ingredient",
            "composition",
            "components",
        ]

        # 1) Tìm box chứa keyword
        key_boxes: List[BBox] = []
        for b in boxes:
            t = b["text"].lower()
            if any(k in t for k in KEYWORDS):
                key_boxes.append(b["bbox"])

        if not key_boxes:
            logger.warning("Không tìm thấy dòng chứa keyword 'Thành phần/Ingredients'.")
            return None

        # Lấy box cao nhất (y nhỏ nhất)
        def bbox_top(bbox: BBox) -> float:
            return min(p[1] for p in bbox)

        key_boxes_sorted = sorted(key_boxes, key=bbox_top)
        ingredient_line = key_boxes_sorted[0]

        y_base = max(p[1] for p in ingredient_line)  # đáy dòng "Thành phần"

        # 2) Gom box bên dưới
        text_boxes_below: List[BBox] = []
        for b in boxes:
            bbox = b["bbox"]
            top = min(p[1] for p in bbox)
            if top > y_base + 5:  # nằm dưới dòng "Thành phần"
                text_boxes_below.append(bbox)

        if not text_boxes_below:
            logger.warning("Không tìm thấy text bên dưới dòng Thành phần.")
            return None

        xs, ys, xe, ye = [], [], [], []
        for bb in text_boxes_below:
            xs.extend([p[0] for p in bb])
            ys.extend([p[1] for p in bb])
            xe.extend([p[0] for p in bb])
            ye.extend([p[1] for p in bb])

        left = max(0, int(min(xs)) - 10)
        right = min(w, int(max(xe)) + 10)
        top = max(0, int(y_base) + 5)
        bottom = min(h, int(max(ye)) + 10)

        if right <= left or bottom <= top:
            return None

        return left, top, right, bottom

    # -----------------------------
    # 4. Hàm OCR THÀNH PHẦN TỔNG QUÁT
    # -----------------------------
    def extract_ingredient_text(
        self, image_path: str
    ) -> Tuple[Optional[str], Optional[Tuple[int, int, int, int]]]:
        """
        Trả về:
          - text thành phần (nếu tìm được)
          - bbox (left, top, right, bottom) của vùng thành phần
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Không tìm thấy file: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Không thể đọc ảnh: {image_path}")

        bbox = self.find_ingredient_region(img)
        if bbox is None:
            return None, None

        left, top, right, bottom = bbox
        roi = img[top:bottom, left:right]

        text = self.ocr_region_ensemble(roi)
        if not text.strip():
            return None, bbox

        # Làm sạch text
        text = text.replace("\r", "").strip()

        return text, bbox

    # -----------------------------
    # 5. OCR toàn ảnh (fallback)
    # -----------------------------
    def ocr_full_image(self, image_path: str) -> str:
        """
        OCR toàn bộ ảnh (khi không tìm được vùng thành phần).
        Dùng ensemble để cải thiện độ chính xác.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Không tìm thấy file: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Không thể đọc ảnh: {image_path}")

        return self.ocr_region_ensemble(img)


# -----------------------------
# 6. API Public: GIỮ NGUYÊN TÊN HÀM
# -----------------------------

# Tạo 1 pipeline global để tái sử dụng (không init lại nhiều lần)
_PIPELINE: Optional[OCRPipeline] = None


def _get_pipeline() -> OCRPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        # Hiện tại môi trường của bạn là CPU, nên use_gpu=True
        # cũng sẽ fallback về CPU. Để đó sẵn, sau này đổi env thì xài lại.
        _PIPELINE = OCRPipeline(use_gpu=False)
    return _PIPELINE


def extract_text_from_image(image_path: str) -> str:
    """
    Hàm public được dùng trong analyze_ecode.py

    Ưu tiên:
      1. Tìm vùng THÀNH PHẦN → OCR → trả text
      2. Nếu không tìm thấy, fallback: OCR toàn ảnh

    Return:
        Chuỗi text vùng thành phần (hoặc toàn ảnh nếu không tìm được vùng).
    """
    pipeline = _get_pipeline()

    try:
        text, bbox = pipeline.extract_ingredient_text(image_path)
        if text and text.strip():
            logger.info(f"OCR thành phần thành công. BBox: {bbox}")
            return text.strip()
        else:
            logger.info(
                "Không trích được vùng thành phần rõ ràng, fallback OCR toàn ảnh."
            )
            return pipeline.ocr_full_image(image_path)
    except Exception as e:
        logger.error(f"Lỗi khi extract_text_from_image: {e}")
        # Fallback cứng: OCR toàn ảnh bằng Tesseract
        try:
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return pytesseract.image_to_string(
                gray, lang="eng+vie", config="--psm 6"
            )
        except Exception as e2:
            logger.error(f"Fallback Tesseract cũng lỗi: {e2}")
            return ""


# -----------------------------
# 7. Test nhanh
# -----------------------------
if __name__ == "__main__":
    # Thay đường dẫn ảnh test của bạn vào đây
    test_path = r"C:\Users\Hanyoo\Downloads\z7244363325262_20ed8e6871fbb3e7848869df5528d7e9.jpg"
    print("File tồn tại:", os.path.exists(test_path))

    txt = extract_text_from_image(test_path)
    print("\n===== TEXT THÀNH PHẦN (HOẶC TOÀN ẢNH) =====")
    print(txt)
    