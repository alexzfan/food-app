from pathlib import Path

from celery import shared_task

from . import facets, ml_client, youtube
from .models import ExtractionJob, Recipe, Video


def _set(job, status, label=""):
    job.status = status
    job.step_label = label
    # Full save so fields set just before the transition (recipe, error) persist.
    job.save()


@shared_task
def run_extraction_job(job_id, file_path=None, transcript=None):
    job = ExtractionJob.objects.get(pk=job_id)
    try:
        if transcript is None:
            _set(job, ExtractionJob.Status.TRANSCRIBING, "Transcribing audio...")
            data = Path(file_path).read_bytes()
            result = ml_client.transcribe(data, Path(file_path).name)
            transcript = result["transcript"]

        _set(job, ExtractionJob.Status.EXTRACTING, "Extracting recipe...")
        summary = ml_client.extract(transcript, job.title or None)

        # Persist the transcript only for caption sources: it's [seconds]-tagged
        # and powers tap-to-seek. Pasted/transcribed text isn't timestamped and
        # nothing reads it back, so storing it would just retain arbitrary text.
        stored_transcript = (
            transcript
            if job.source == ExtractionJob.Source.YOUTUBE_CAPTIONS
            else ""
        )
        # Carry the source channel and thumbnail onto the recipe so the detail
        # view can credit it and cookbook cards can show an image. Both live on
        # the cached Video (keyed by video id) from the search that surfaced
        # this clip; best-effort -- a pruned/absent cache row falls back to the
        # deterministic thumbnail URL and a blank credit.
        channel_name = ""
        thumbnail = ""
        if job.youtube_video_id:
            video = Video.objects.filter(video_id=job.youtube_video_id).first()
            if video:
                channel_name = video.channel_title
                thumbnail = video.thumbnail_url
            if not thumbnail:
                thumbnail = youtube.thumbnail_url(job.youtube_video_id)
        recipe = Recipe.objects.create(
            owner=job.owner,
            youtube_video_id=job.youtube_video_id,
            channel_name=channel_name,
            thumbnail_url=thumbnail,
            transcript=stored_transcript or "",
            title=summary["title"],
            description=summary.get("description", ""),
            ingredients=summary.get("ingredients", []),
            instructions=summary.get("instructions", []),
            tags=summary.get("tags", []),
            cuisine=summary.get("cuisine", "") or "",
            cook_time_minutes=summary.get("cook_time_minutes"),
            prep_time_minutes=summary.get("prep_time_minutes"),
            servings=summary.get("servings"),
            difficulty=summary.get("difficulty", "") or "",
            meal_type=facets.normalize_meal_type(summary.get("meal_type", "")),
            dietary=facets.normalize_dietary(summary.get("dietary", [])),
        )
        job.recipe = recipe
        _set(job, ExtractionJob.Status.DONE, "Done")
    except Exception as e:  # noqa: BLE001
        job.error = str(e)
        _set(job, ExtractionJob.Status.FAILED, "Failed")
    finally:
        if file_path:
            Path(file_path).unlink(missing_ok=True)
