# 📂 Thư mục `src/` – Source Code Chính

Thư mục này chứa toàn bộ mã nguồn lõi của hệ thống **Phân loại & Cảnh báo mức độ an toàn phụ gia thực phẩm (E-code)**.  
Các module trong đây đảm nhận từng giai đoạn trong pipeline xử lý dữ liệu: từ OCR, NLP, tri thức Neo4j cho đến áp dụng Rule Engine và phân tích kết quả.

---

## ⚙️ 1. Cấu trúc tổng quan

src/
├── init.py
├── ocr_module.py # Nhận diện văn bản từ ảnh (OCR)
├── nlp_module.py # Chuẩn hóa & nhận dạng mã E-code từ text
├── neo4j_connector.py # Kết nối và truy vấn dữ liệu tri thức trong Neo4j
├── rule_engine.py # Áp dụng bộ luật (risk_rules.yaml) để gán mức rủi ro
├── analyze_ecode.py # Pipeline chính kết hợp NLP + KG + Rule
└── utils.py # Hàm tiện ích chung (load, log, lưu kết quả)


---

## 🧩 2. Mô tả chi tiết từng module

### 🖼️ `ocr_module.py`
- **Chức năng:** Nhận diện văn bản (tên phụ gia, mã E-code, thành phần) từ ảnh nhãn sản phẩm.  
- **Công nghệ:** `EasyOCR` hoặc `Tesseract`.  
- **Đầu vào:** Ảnh `.jpg`, `.png` trong thư mục `data/sample_inputs/`.  
- **Đầu ra:** Chuỗi văn bản thu được từ ảnh.

---

### 🧠 `nlp_module.py`
- **Chức năng:** Tiền xử lý văn bản OCR, chuẩn hóa & trích xuất danh sách E-code.  
- **Công việc chính:**
  - Dùng regex nhận dạng các chuỗi như `E102`, `E211`, `E300`, ...
  - Liên kết E-code với thông tin trong `ecodes_master.csv` (CommonName, Category, RiskLevel).
- **Đầu ra:** Danh sách các phụ gia có trong văn bản.

---

### 🕸️ `neo4j_connector.py`
- **Chức năng:** Kết nối với cơ sở dữ liệu **Neo4j**, truy vấn tri thức về từng E-code.  
- **Truy vấn chính:**
  - `Category`, `Effects`, `RiskLevel`, `ADI_mgkg`, `BannedIn`.  
- **Đầu ra:** Một dictionary chứa đầy đủ thông tin tri thức về phụ gia.

---

### ⚖️ `rule_engine.py`
- **Chức năng:** Đọc file `rules/risk_rules.yaml`, áp dụng các điều kiện rule (if–then) để xác định mức độ an toàn.  
- **Các loại rule:**
  - `explicit_avoid` → Tránh dùng hoàn toàn.  
  - `banned_country` → Bị cấm tại quốc gia lớn.  
  - `low_adi_overuse` → Lượng vượt ngưỡng ADI.  
  - `category_colorant` → Phẩm màu nhân tạo cần thận trọng.  
- **Đầu ra:** `risk` (Safe / Caution / Avoid) + `reason`.

---

### 🔍 `analyze_ecode.py`
- **Chức năng:** Pipeline tổng hợp toàn bộ quy trình:
  1. OCR (hoặc nhập text)
  2. NLP → trích E-code
  3. Truy vấn Neo4j → lấy thông tin tri thức
  4. Rule Engine → gán mức cảnh báo
- **Đầu ra:** Danh sách E-code kèm `RiskLevel`, `Reason`, `Category`, `Effects`, `BannedIn`.

---

### 🧰 utils.py
- **Chức năng:** Các hàm tiện ích dùng chung:

  1. load_yaml(path) – Đọc file YAML rule.
  2. save_json(data, path) – Lưu kết quả phân tích.
  3. log(msg) – Ghi log có timestamp.


    Ví dụ:
    ```json
    {
    "ECode": "E102",
    "CommonName": "Tartrazine",
    "Category": "Colorant",
    "RiskLevel": "Avoid",
    "Effects": ["allergy", "hyperactivity"],
    "BannedIn": ["NO", "AT"],
    "reason": "Phụ gia có tác dụng phụ nghiêm trọng (dị ứng, ảnh hưởng thần kinh)"
    }

---

## 🚀 3. Cách chạy thử pipeline

    from src.analyze_ecode import analyze_ecode
    print(analyze_ecode("Contains E102 and E211"))

**Kết quả đầu ra mẫu:**
    [
        {"ECode": "E102", "risk": "Avoid", "reason": "Phụ gia có tác dụng phụ nghiêm trọng"},
        {"ECode": "E211", "risk": "Caution", "reason": "Chất bảo quản nên hạn chế với trẻ nhỏ"}
    ]
