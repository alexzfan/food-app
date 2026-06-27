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


@login_required
@onboarding_required
def discover(request):
    return render(request, "recipes/discover.html")


@login_required
@onboarding_required
def youtube_search(request):
    query = request.GET.get("q", "").strip()
    videos = []
    error = None
    if query:
        try:
            videos = youtube.search_recipe_videos(query)["videos"]
        except Exception:
            error = "Search failed. Try again."
    return render(
        request, "recipes/_results.html", {"videos": videos, "error": error, "query": query}
    )


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
