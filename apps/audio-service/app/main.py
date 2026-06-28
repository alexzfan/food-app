import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .extractor import get_extractor
from .transcription import probe_duration, transcribe_file

logger = logging.getLogger("recipe-ml")

app = FastAPI(title="Recipe ML Service", version="2.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(200 * 1024 * 1024)))
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", "900"))
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
        duration = probe_duration(str(tmp_path))
        if duration > MAX_DURATION_SECONDS:
            raise HTTPException(
                status_code=400,
                detail=f"Media too long ({int(duration)}s). Max: {MAX_DURATION_SECONDS}s",
            )
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
        # Log the real cause + traceback server-side; a bare 502 in the access
        # log is undiagnosable. The cause is also returned in the detail.
        logger.exception("extract failed")
        raise HTTPException(status_code=502, detail=f"Extraction failed: {e}")
