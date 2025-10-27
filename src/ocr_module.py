import easyocr

def extract_text_from_image(image_path: str) -> str:
    """
    Đọc văn bản trên nhãn sản phẩm từ ảnh.
    """
    reader = easyocr.Reader(['en'])
    results = reader.readtext(image_path)
    text = " ".join([res[1] for res in results])
    return text