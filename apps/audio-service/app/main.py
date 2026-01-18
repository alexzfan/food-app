"""
Audio Extraction & Transcription Service
Extracts audio from YouTube videos using yt-dlp and transcribes with Whisper
"""

import os
import tempfile
import logging
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
from faster_whisper import WhisperModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Extraction & Transcription Service",
    description="Extract audio from YouTube videos and transcribe for recipe extraction",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp directory for audio files
TEMP_DIR = Path(tempfile.gettempdir()) / "recipe-audio"
TEMP_DIR.mkdir(exist_ok=True)

# Max video duration (15 minutes) to prevent abuse
MAX_DURATION_SECONDS = int(os.environ.get("MAX_DURATION_SECONDS", 900))

# Whisper model - using "base" for balance of speed/accuracy
# Options: tiny, base, small, medium, large-v3
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")

# Global Whisper model instance (loaded lazily)
_whisper_model: Optional[WhisperModel] = None


def get_whisper_model() -> WhisperModel:
    """Get or initialize the Whisper model"""
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
        _whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",  # Use "cuda" if GPU available
            compute_type="int8",  # Use "float16" for GPU
        )
        logger.info("Whisper model loaded successfully")
    return _whisper_model


class VideoInfo(BaseModel):
    """Video information response"""
    video_id: str
    title: str
    duration: int
    channel: str
    thumbnail: Optional[str] = None


class TranscriptResponse(BaseModel):
    """Transcription response"""
    video_id: str
    title: str
    duration: int
    transcript: str
    language: str


def get_yt_dlp_opts(output_path: str) -> dict:
    """Get yt-dlp options for audio extraction"""
    return {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",  # Whisper prefers WAV
            "preferredquality": "0",  # Best quality
        }],
        # Limit duration
        "match_filter": yt_dlp.utils.match_filter_func(
            f"duration < {MAX_DURATION_SECONDS}"
        ),
    }


def cleanup_file(file_path: str):
    """Remove temporary file after response is sent"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to cleanup {file_path}: {e}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "audio-transcription"}


@app.get("/video/{video_id}/info", response_model=VideoInfo)
async def get_video_info(video_id: str):
    """Get video information without downloading"""
    url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                raise HTTPException(status_code=404, detail="Video not found")

            duration = info.get("duration", 0)

            if duration > MAX_DURATION_SECONDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Video too long. Max duration: {MAX_DURATION_SECONDS}s ({MAX_DURATION_SECONDS // 60} min)"
                )

            return VideoInfo(
                video_id=video_id,
                title=info.get("title", "Unknown"),
                duration=duration,
                channel=info.get("channel", info.get("uploader", "Unknown")),
                thumbnail=info.get("thumbnail"),
            )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp error for {video_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get video info")


@app.get("/video/{video_id}/transcript", response_model=TranscriptResponse)
async def transcribe_video(video_id: str, background_tasks: BackgroundTasks):
    """
    Download audio from YouTube video and transcribe it.

    Returns the transcript text that can be used for recipe extraction.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = str(TEMP_DIR / f"{video_id}.%(ext)s")
    wav_path = str(TEMP_DIR / f"{video_id}.wav")

    try:
        # Get video info first
        info_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                raise HTTPException(status_code=404, detail="Video not found")

            duration = info.get("duration", 0)
            title = info.get("title", "Unknown")

            if duration > MAX_DURATION_SECONDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Video too long ({duration}s). Max: {MAX_DURATION_SECONDS}s"
                )

        # Download and extract audio as WAV
        logger.info(f"Downloading audio for {video_id}")
        ydl_opts = get_yt_dlp_opts(output_template)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the WAV file
        if not os.path.exists(wav_path):
            # Check for other extensions and convert if needed
            for ext in ["m4a", "webm", "opus", "mp3"]:
                alt_path = str(TEMP_DIR / f"{video_id}.{ext}")
                if os.path.exists(alt_path):
                    wav_path = alt_path
                    break

        if not os.path.exists(wav_path):
            raise HTTPException(
                status_code=500,
                detail="Audio extraction failed - file not found"
            )

        # Transcribe with Whisper
        logger.info(f"Transcribing audio for {video_id}")
        model = get_whisper_model()

        segments, info = model.transcribe(
            wav_path,
            beam_size=5,
            language=None,  # Auto-detect language
            vad_filter=True,  # Filter out non-speech
        )

        # Combine segments into full transcript
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text.strip())

        transcript = " ".join(transcript_parts)
        detected_language = info.language

        logger.info(f"Transcription complete for {video_id}: {len(transcript)} chars, language: {detected_language}")

        # Schedule cleanup
        background_tasks.add_task(cleanup_file, wav_path)

        return TranscriptResponse(
            video_id=video_id,
            title=title,
            duration=duration,
            transcript=transcript,
            language=detected_language,
        )

    except HTTPException:
        raise
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error for {video_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error transcribing video: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@app.get("/video/{video_id}/audio")
async def get_audio(video_id: str, background_tasks: BackgroundTasks):
    """
    Download and return audio file (for debugging or alternative processing).
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = str(TEMP_DIR / f"{video_id}_audio.%(ext)s")

    try:
        # Check video info first
        info_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            if info is None:
                raise HTTPException(status_code=404, detail="Video not found")

            duration = info.get("duration", 0)
            if duration > MAX_DURATION_SECONDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Video too long ({duration}s). Max: {MAX_DURATION_SECONDS}s"
                )

            title = info.get("title", "audio")

        # Download audio
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "128",
            }],
            "match_filter": yt_dlp.utils.match_filter_func(
                f"duration < {MAX_DURATION_SECONDS}"
            ),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find output file
        audio_path = None
        for ext in ["m4a", "webm", "opus", "mp3", "wav"]:
            check_path = TEMP_DIR / f"{video_id}_audio.{ext}"
            if check_path.exists():
                audio_path = check_path
                break

        if audio_path is None:
            raise HTTPException(status_code=500, detail="Audio extraction failed")

        # Schedule cleanup
        background_tasks.add_task(cleanup_file, str(audio_path))

        return FileResponse(
            path=str(audio_path),
            media_type="audio/mp4",
            filename=f"{title}.m4a",
            headers={
                "X-Video-ID": video_id,
                "X-Duration": str(duration),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        raise HTTPException(status_code=500, detail="Audio extraction failed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
