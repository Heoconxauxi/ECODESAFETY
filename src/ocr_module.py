from __future__ import annotations
import os
import logging
from typing import List, Tuple, Optional, Dict, Any

import cv2
import numpy as np
import pytesseract

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s - %(message)s")

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

try:
    import easyocr
except ImportError:
    easyocr = None


BBox = List[List[float]]


class OCRBackendUnavailable(Exception):
    pass


class OCRPipeline:
    def __init__(self, use_gpu: bool = False) -> None:
        self.use_gpu = use_gpu
        self.ppocr = None
        self.easy_reader = None

        if PaddleOCR:
            try:
                self.ppocr = PaddleOCR(
                    lang="vi",
                    use_textline_orientation=True,
                    show_log=False
                )
                logger.info("PaddleOCR OK")
            except:
                self.ppocr = None

        if easyocr:
            try:
                self.easy_reader = easyocr.Reader(["vi", "en"], gpu=use_gpu)
                logger.info("EasyOCR OK")
            except:
                self.easy_reader = None

    def detect_boxes_with_text(self, img: np.ndarray) -> List[Dict[str, Any]]:
        boxes = []

        if self.ppocr:
            try:
                result = self.ppocr.ocr(img, cls=True)
                for group in result:
                    for line in group:
                        bbox = line[0]
                        txt = line[1][0]
                        conf = float(line[1][1])
                        boxes.append({"bbox": bbox, "text": txt, "conf": conf})
                return boxes
            except:
                pass

        if self.easy_reader:
            try:
                result = self.easy_reader.readtext(img)
                for (bbox, txt, conf) in result:
                    boxes.append({"bbox": bbox, "text": txt, "conf": float(conf)})
                return boxes
            except:
                pass

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
            bbox = [[x, y], [x+w, y], [x+w, y+h], [x, y+h]]
            boxes.append({"bbox": bbox, "text": txt, "conf": conf})
        return boxes

    def ocr_region_ensemble(self, roi: np.ndarray) -> str:
        candidates = []

        if self.ppocr:
            try:
                res = self.ppocr.ocr(roi, cls=True)
                texts = []
                for group in res:
                    for line in group:
                        texts.append(line[1][0])
                if texts:
                    candidates.append(" ".join(texts).strip())
            except:
                pass

        if self.easy_reader:
            try:
                res = self.easy_reader.readtext(roi, detail=0)
                if res:
                    candidates.append(" ".join(res).strip())
            except:
                pass

        try:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        except:
            gray = roi

        try:
            tess = pytesseract.image_to_string(gray, lang="eng+vie", config="--psm 6").strip()
            if tess:
                candidates.append(tess)
        except:
            pass

        if not candidates:
            return ""

        norm = [c.strip() for c in candidates if c.strip()]
        if not norm:
            return ""
        for c in norm:
            if norm.count(c) >= 2:
                return c
        return max(norm, key=len)

    def find_ingredient_region(self, img: np.ndarray) -> Optional[Tuple[int,int,int,int]]:
        h, w = img.shape[:2]
        boxes = self.detect_boxes_with_text(img)
        if not boxes:
            return None

        key = ["thành phần", "ingredients", "ingredient", "composition", "components"]
        key_boxes = [b["bbox"] for b in boxes if any(k in b["text"].lower() for k in key)]
        if not key_boxes:
            return None

        def top(bb): return min(p[1] for p in bb)
        key_boxes.sort(key=top)
        base_box = key_boxes[0]
        y_base = max(p[1] for p in base_box)

        below = []
        for b in boxes:
            y = min(p[1] for p in b["bbox"])
            if y > y_base + 5:
                below.append(b["bbox"])

        if not below:
            return None

        xs = [p[0] for bb in below for p in bb]
        ys = [p[1] for bb in below for p in bb]
        left = max(0, int(min(xs)) - 5)
        right = min(w, int(max(xs)) + 5)
        top = max(0, int(y_base) + 5)
        bottom = min(h, int(max(ys)) + 5)

        if right <= left or bottom <= top:
            return None

        return left, top, right, bottom

    def extract_ingredient_text(self, image_path: str):
        if not os.path.exists(image_path):
            raise FileNotFoundError

        img = cv2.imread(image_path)
        if img is None:
            raise ValueError

        bbox = self.find_ingredient_region(img)
        if not bbox:
            return None, None

        l, t, r, b = bbox
        roi = img[t:b, l:r]
        text = self.ocr_region_ensemble(roi)
        return (text.strip() if text else None), bbox

    def ocr_full_image(self, image_path: str) -> str:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError
        return self.ocr_region_ensemble(img)


_PIPELINE: Optional[OCRPipeline] = None


def _get_pipeline() -> OCRPipeline:
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = OCRPipeline(use_gpu=False)
    return _PIPELINE


def extract_text_from_image(image_path: str) -> str:
    pipeline = _get_pipeline()
    try:
        text, bbox = pipeline.extract_ingredient_text(image_path)
        if text:
            return text
        return pipeline.ocr_full_image(image_path)
    except:
        try:
            img = cv2.imread(image_path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return pytesseract.image_to_string(gray, lang="eng+vie", config="--psm 6")
        except:
            return ""
