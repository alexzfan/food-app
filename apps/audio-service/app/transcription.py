import json
import os
import subprocess
from typing import Optional

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
_model: Optional[object] = None


def probe_duration(path: str) -> float:
    """Return media duration in seconds via ffprobe.

    Best-effort: returns 0.0 when ffprobe is missing or the file can't be
    probed, so environments without ffmpeg (e.g. local test runs) don't reject
    valid uploads. Real enforcement happens in the Docker image where ffmpeg
    is installed.
    """
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode != 0:
            return 0.0
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def get_model():
    global _model
    if _model is None:
        # Imported lazily so the test suite never loads the heavy model lib.
        from faster_whisper import WhisperModel

        _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def transcribe_file(path: str) -> dict:
    model = get_model()
    segments, info = model.transcribe(path, beam_size=5, language=None, vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments)
    return {
        "transcript": text,
        "language": info.language,
        "duration": float(getattr(info, "duration", 0.0)),
    }
