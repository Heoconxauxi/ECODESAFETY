import easyocr
import os
import cv2

# Khởi tạo OCR 1 lần cho nhanh
reader = easyocr.Reader(['en', 'vi'])


def extract_text_from_image(image_path: str) -> str:
    """
    OCR toàn ảnh → tìm 'Thành phần / Ingredients' → crop vùng bên dưới → OCR lại.
    GIỮ NGUYÊN TÊN HÀM NHƯ BẠN YÊU CẦU.
    """

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Không tìm thấy file: {image_path}")

    # Đọc ảnh
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Không thể đọc ảnh: {image_path}")

    print("Ảnh đọc thành công:", img.shape)

    # ==== STEP 1: OCR TOÀN ẢNH ====
    results = reader.readtext(img)

    # ==== STEP 2: TÌM BLOCK CÓ TỪ 'THÀNH PHẦN' ====
    keywords = ["thành phần", "ingredients", "ingredient"]
    ingredient_bbox = None

    for bbox, text, conf in results:
        lower = text.lower()
        if any(k in lower for k in keywords):
            ingredient_bbox = bbox
            print("Đã tìm thấy block thành phần:", text)
            break

    if ingredient_bbox is None:
        return "Không tìm thấy mục THÀNH PHẦN trên nhãn."

    # ==== STEP 3: CROP VÙNG BÊN DƯỚI BLOCK ====
    # bbox: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    (x1, y1) = ingredient_bbox[0]
    (_, y2) = ingredient_bbox[2]

    h, w = img.shape[:2]

    # Crop từ block xuống khoảng 600px (có thể chỉnh)
    top = int(y2)
    bottom = min(h, int(y2 + 600))

    # Mở rộng ngang
    left = 0
    right = w

    crop = img[top:bottom, left:right]

    # Debug
    # cv2.imwrite("debug_crop.png", crop)

    # ==== STEP 4: OCR LẠI CHỈ VÙNG CROP ====
    ingredient_results = reader.readtext(crop, detail=0)

    ingredient_text = "\n".join(ingredient_results)

    return ingredient_text



# ---- TEST ----
if __name__ == "__main__":
    image_path = "data/sample_inputs/20251029_182156.jpg"
    print("File tồn tại:", os.path.exists(image_path))

    text = extract_text_from_image(image_path)
    print("\n===== TEXT THÀNH PHẦN =====")
    print(text)
