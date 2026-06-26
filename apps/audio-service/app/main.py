import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .extractor import get_extractor
from .transcription import transcribe_file

app = FastAPI(title="Recipe ML Service", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
TEMP_DIR = Path(tempfile.gettempdir()) / "recipe-uploads"
TEMP_DIR.mkdir(exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "recipe-ml"}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    suffix = Path(file.filename or "upload").suffix or ".bin"
    tmp_path = TEMP_DIR / f"{os.urandom(8).hex()}{suffix}"
    try:
        tmp_path.write_bytes(data)
        result = transcribe_file(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)
    return result


class ExtractRequest(BaseModel):
    transcript: str
    title: str | None = None


@app.post("/extract")
async def extract(req: ExtractRequest):
    extractor = get_extractor()
    try:
        return extractor.extract(req.transcript, req.title)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}")
