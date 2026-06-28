from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.views import onboarding_required

from . import youtube
from .models import ExtractionJob, Favorite, Recipe
from .tasks import run_extraction_job

FILTERS = [
    {"key": "all", "label": "All results"},
    {"key": "ready", "label": "Recipe ready"},
    {"key": "extractable", "label": "Extractable"},
    {"key": "under15", "label": "Under 15 min"},
    {"key": "captions", "label": "Has captions"},
]


def _annotate_videos(videos, user):
    ids = [v["id"] for v in videos]
    recipes = {
        r.youtube_video_id: r
        for r in Recipe.objects.filter(owner=user, youtube_video_id__in=ids)
    }
    fav_ids = set(
        Favorite.objects.filter(
            user=user, recipe__youtube_video_id__in=ids
        ).values_list("recipe__youtube_video_id", flat=True)
    )
    for video in videos:
        recipe = recipes.get(video["id"])
        if recipe is not None:
            recipe.is_favorite = video["id"] in fav_ids
        video["recipe"] = recipe


def _apply_filter(videos, key):
    if key == "ready":
        return [v for v in videos if v.get("recipe")]
    if key == "extractable":
        return [v for v in videos if v.get("has_captions") and not v.get("recipe")]
    if key == "under15":
        return [
            v for v in videos
            if v.get("duration_seconds") and v["duration_seconds"] <= 900
        ]
    if key == "captions":
        return [v for v in videos if v.get("has_captions")]
    return videos


def _remember_search(request, query):
    recents = [
        q for q in request.session.get("recent_searches", [])
        if q.lower() != query.lower()
    ]
    recents.insert(0, query)
    request.session["recent_searches"] = recents[:6]


@login_required
@onboarding_required
def discover(request):
    return render(request, "recipes/discover.html")


@login_required
@onboarding_required
def youtube_search(request):
    query = request.GET.get("q", "").strip()
    view = "list" if request.GET.get("view") == "list" else "grid"
    active_filter = request.GET.get("filter", "all")
    videos = []
    error = None
    total = 0
    if query:
        try:
            videos = youtube.search_recipe_videos(query)["videos"]
        except Exception:
            error = "Search failed. Try again."
        total = len(videos)
        _annotate_videos(videos, request.user)
        _remember_search(request, query)
        videos = _apply_filter(videos, active_filter)
    return render(
        request,
        "recipes/_results.html",
        {
            "videos": videos, "error": error, "query": query, "view": view,
            "active_filter": active_filter, "filters": FILTERS,
            "total": total, "shown": len(videos),
        },
    )


@login_required
@onboarding_required
@require_POST
def extract_from_captions(request):
    video_id = request.POST.get("video_id", "")
    title = request.POST.get("title", "")
    transcript = youtube.fetch_transcript(video_id)
    if not transcript:
        return render(
            request,
            "recipes/_extract_fallback.html",
            {"video": {"id": video_id, "title": title}},
        )
    job = ExtractionJob.objects.create(
        owner=request.user,
        source=ExtractionJob.Source.YOUTUBE_CAPTIONS,
        youtube_video_id=video_id,
        title=title,
    )
    run_extraction_job.delay(job.id, transcript=transcript)
    return render(request, "recipes/_job_status.html", {"job": job})


# ---------------------------------------------------------------------------
# Ingestion: start a job from upload / pasted transcript
# ---------------------------------------------------------------------------


@login_required
@onboarding_required
@require_POST
def start_job(request):
    source = request.POST.get("source", "upload")
    job = ExtractionJob.objects.create(
        owner=request.user,
        source=source,
        youtube_video_id=request.POST.get("youtube_video_id", ""),
        title=request.POST.get("title", ""),
    )

    if source == ExtractionJob.Source.PASTE_TRANSCRIPT:
        transcript = request.POST.get("transcript", "").strip()
        run_extraction_job.delay(job.id, transcript=transcript)
    elif source == ExtractionJob.Source.PASTE_TEXT:
        text = request.POST.get("text", "").strip()
        run_extraction_job.delay(job.id, transcript=text)
    else:  # upload
        upload = request.FILES["media"]
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        # Never trust the client filename: derive a safe name from job id + the
        # extension only, so a crafted name like "../../x" can't escape the dir.
        suffix = Path(upload.name).suffix
        tmp_path = upload_dir / f"{job.id}{suffix}"
        with open(tmp_path, "wb") as f:
            for chunk in upload.chunks():
                f.write(chunk)
        run_extraction_job.delay(job.id, file_path=str(tmp_path))

    return render(request, "recipes/_job_status.html", {"job": job})


@login_required
@onboarding_required
def job_status(request, pk):
    job = get_object_or_404(ExtractionJob, pk=pk, owner=request.user)
    if job.status == ExtractionJob.Status.DONE and job.recipe_id:
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = reverse("recipe_detail", args=[job.recipe_id])
        return resp
    return render(request, "recipes/_job_status_poll.html", {"job": job})


# ---------------------------------------------------------------------------
# Saved / favorites / detail
# ---------------------------------------------------------------------------


def _annotated(qs, user):
    fav = Favorite.objects.filter(user=user, recipe=OuterRef("pk"))
    return qs.annotate(is_favorite=Exists(fav))


@login_required
@onboarding_required
def saved(request):
    q = request.GET.get("q", "").strip()
    recipes = _annotated(Recipe.objects.filter(owner=request.user), request.user)
    if q:
        recipes = recipes.filter(title__icontains=q)
    return render(request, "recipes/saved.html", {"recipes": recipes, "q": q})


@login_required
@onboarding_required
def favorites(request):
    recipes = _annotated(
        Recipe.objects.filter(owner=request.user, favorited_by__user=request.user),
        request.user,
    )
    return render(request, "recipes/favorites.html", {"recipes": recipes})


@login_required
@onboarding_required
def recipe_detail(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    recipe.is_favorite = Favorite.objects.filter(
        user=request.user, recipe=recipe
    ).exists()
    return render(request, "recipes/detail.html", {"recipe": recipe})


@login_required
@onboarding_required
@require_POST
def toggle_favorite(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    fav, created = Favorite.objects.get_or_create(user=request.user, recipe=recipe)
    if not created:
        fav.delete()
    recipe.is_favorite = created
    # The detail page swaps just the button; list pages swap the whole card.
    if request.POST.get("context") == "detail":
        template = "recipes/_favorite_button.html"
    elif request.POST.get("context") == "search":
        template = "recipes/_save_button.html"
    else:
        template = "recipes/_recipe_card.html"
    return render(request, template, {"recipe": recipe})


@login_required
@onboarding_required
@require_POST
def delete_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    recipe.delete()
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("saved")
    return resp
