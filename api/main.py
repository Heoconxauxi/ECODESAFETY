from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from src.analyze_ecode import analyze_ecode
from api.schemas import AnalysisResult, AnalyzeTextInput, EcodeAnalysis
import tempfile, os

app = FastAPI(
    title="EcodeSafety API",
    description="API phân tích E-code từ Text hoặc Ảnh.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- TEXT INPUT ---
@app.post("/ecode/analyze", response_model=AnalysisResult)
async def analyze_product_ingredients_text(input_data: AnalyzeTextInput):
    try:
        source_text = input_data.input_text
        analysis_output = analyze_ecode(source_text)
        results = analysis_output.get('analysis_results', [])

        ecodes_found = [
            EcodeAnalysis(
                ecode=res.get('ECode', 'N/A'),
                name_vn=res.get('CommonName', 'N/A'),
                category=res.get('Category', 'N/A'),
                safety_level=res.get('risk', 'Unknown'),
                warnings=[res.get('reason', 'Không có cảnh báo chi tiết.')]
            )
            for res in results
        ]

        return AnalysisResult(
            status="SUCCESS",
            input_type="TEXT_INPUT",
            source_text=analysis_output.get('source_text', source_text),
            ecodes_found=ecodes_found
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý API Text: {str(e)}")

# --- IMAGE INPUT ---
@app.post("/ecode/analyze_image", response_model=AnalysisResult)
async def analyze_product_image(image_file: UploadFile = File(...)):
    temp_file_path = None
    try:
        suffix = f".{image_file.filename.split('.')[-1]}" if '.' in image_file.filename else ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await image_file.read())
            temp_file_path = tmp.name

        analysis_output = analyze_ecode(temp_file_path)
        results = analysis_output.get('analysis_results', [])

        ecodes_found = [
            EcodeAnalysis(
                ecode=res.get('ECode', 'N/A'),
                name_vn=res.get('CommonName', 'N/A'),
                category=res.get('Category', 'N/A'),
                safety_level=res.get('risk', 'Unknown'),
                warnings=[res.get('reason', 'Không có cảnh báo chi tiết.')]
            )
            for res in results
        ]

        return AnalysisResult(
            status="SUCCESS",
            input_type="IMAGE_INPUT",
            source_text=analysis_output.get('source_text', 'OCR Failed.'),
            ecodes_found=ecodes_found
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý ảnh: {str(e)}")

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
