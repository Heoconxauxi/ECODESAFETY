    EcodeSafety/
    │
    ├── 📁 data/
    │   ├── E-number.csv                 # File gốc (raw)
    │   ├── ecodes_master.csv            # File chuẩn hóa (đã xử lý ở bước 1)
    │   ├── sample_inputs/               # Ảnh, nhãn sản phẩm OCR
    │   └── outputs/                     # Kết quả chạy thử nghiệm (JSON, CSV)
    │
    ├── 📁 ontology/
    │   ├── schema.json                  # Định nghĩa lớp, quan hệ, constraint
    │   └── mapping_notes.md             # Ghi chú mapping từ CSV → Ontology
    │
    ├── 📁 rules/
    │   └── risk_rules.yaml              # Bộ luật cảnh báo mức độ an toàn
    │
    ├── 📁 src/
    │   ├── __init__.py
    │   ├── ocr_module.py                # OCR (EasyOCR, Tesseract)
    │   ├── nlp_module.py                # Chuẩn hóa tên phụ gia, nhận dạng E-code
    │   ├── neo4j_connector.py           # Hàm kết nối và truy vấn Neo4j
    │   ├── rule_engine.py               # evaluate_rules() (đã làm ở bước 3)
    │   ├── analyze_ecode.py             # Hàm chính: combine NLP + KG + Rule
    │   └── utils.py                     # Các hàm phụ: đọc YAML, logging, v.v.
    │
    ├── 📁 api/
    │   ├── main.py                      # FastAPI — cung cấp endpoint /ecode/analyze
    │   └── requirements.txt             # Thư viện cần thiết (neo4j, pyyaml, fastapi, uvicorn,...)
    │
    ├── 📁 app_ui/
    │   ├── web/                         # Giao diện web (HTML/CSS/JS hoặc Flask)
    │   └── mobile/                      # Giao diện Flutter (nếu làm đa nền tảng)
    │
    ├── 📁 tests/
    │   ├── test_rule_engine.py          # Kiểm thử evaluate_rules()
    │   ├── test_neo4j_integration.py    # Kiểm thử truy vấn từ Neo4j
    │   └── test_end_to_end.py           # OCR → NLP → KG → Rule pipeline
    │
    ├── 📁 docs/
    │   ├── de_cuong_chi_tiet.docx       # Mẫu đề cương chính thức
    │   ├── phieu_dang_ky_de_tai.docx
    │   ├── weekly_plan.xlsx             # Kế hoạch theo tuần (GVHD yêu cầu)
    │   ├── diagrams/
    │   │   ├── architecture.drawio      # Sơ đồ pipeline OCR→NLP→KG→Rule
    │   │   ├── ontology_structure.png   # Sơ đồ Ontology (Class + Relation)
    │   │   └── dataflow.png             # Dòng chảy dữ liệu
    │   └── references.bib               # Tài liệu tham khảo
    │
    ├── 📁 notebooks/
    │   ├── 01_data_cleaning.ipynb       # Chuẩn hóa CSV (bước 1)
    │   ├── 02_ontology_and_neo4j.ipynb  # Nạp KG (bước 2)
    │   ├── 03_rule_engine.ipynb         # Rule-based (bước 3)
    │   ├── 04_api_demo.ipynb            # API + Demo kết quả
    │   └── 05_visualization.ipynb       # Vẽ đồ thị quan hệ trong Neo4j
    │
    ├── .gitignore
    ├── README.md                        # Giới thiệu tổng quan dự án
    └── setup_env.bat / setup_env.sh     # Script tạo môi trường ảo & cài thư viện
