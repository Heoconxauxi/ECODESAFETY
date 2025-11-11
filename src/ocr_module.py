import easyocr
import os
import cv2

def extract_text_from_image(image_path: str) -> str:
    """
    Đọc văn bản trên nhãn sản phẩm từ ảnh.
    """
    reader = easyocr.Reader(['en'])

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Không tìm thấy file: {image_path}")

    # Thử đọc ảnh trực tiếp bằng OpenCV
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Không thể đọc ảnh (ảnh có thể bị lỗi hoặc đường dẫn chứa ký tự đặc biệt): {image_path}")

    # Nếu ảnh đọc được, in thông tin
    print("Ảnh đọc thành công:", img.shape)

    # Dùng EasyOCR với ảnh đọc sẵn thay vì đường dẫn
    results = reader.readtext(img)
    text = " ".join([res[1] for res in results])
    return text


# ---- TEST ----
if __name__ == "__main__":
    image_path = "data/sample_inputs/20251029_182156.jpg"
    print("File tồn tại:", os.path.exists(image_path))
    text = extract_text_from_image(image_path)
    print("Văn bản trích xuất được:")
    print(text)
