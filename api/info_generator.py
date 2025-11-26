from google import genai

client = genai.Client(api_key="AIzaSyBltTGvqVUMeIGLrSh2xmNmDYc1sP76bRw")


async def generate_additive_info(ins: str, name: str, name_vn: str = None) -> str:

    prompt = f"""
    Hãy mô tả phụ gia thực phẩm mã {ins} ({name_vn or name}).
    Trả lời súc tích 3–5 câu:
    - Nguồn gốc
    - Công dụng
    - Nguy cơ sức khỏe (nếu có)
    - Tình trạng được phép sử dụng tại Việt Nam và quốc tế
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text.strip()
