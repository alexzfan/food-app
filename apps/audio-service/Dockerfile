# Audio Extraction & Transcription Service Dockerfile
FROM python:3.11-slim

# Install ffmpeg (required for yt-dlp and whisper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Note: Whisper model will be downloaded on first use (~150MB for base model)
# To pre-download, uncomment the next line (adds ~2 min to build time):
# RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

# Copy application code
COPY app/ ./app/

# Create temp directory for audio files
RUN mkdir -p /tmp/recipe-audio

# Environment variables
ENV WHISPER_MODEL_SIZE=base
ENV MAX_DURATION_SECONDS=900

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
