import os
from typing import Optional

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
_model: Optional[object] = None


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
