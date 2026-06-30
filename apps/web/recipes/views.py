from collections import Counter
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.views import onboarding_required

from . import facets, search_cache, youtube
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


def _mmss(seconds):
    """Whole seconds -> "m:ss" display, or "" for None. e.g. 135 -> "2:15"."""
    if seconds is None:
        return ""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


@login_required
@onboarding_required
def discover(request):
    return render(
        request,
        "recipes/discover.html",
        {
            "trending": youtube.TRENDING,
            "cuisines": youtube.CUISINES,
            "recent_searches": request.session.get("recent_searches", []),
        },
    )


@login_required
@onboarding_required
def suggest(request):
    q = request.GET.get("q", "").strip()
    return render(
        request,
        "recipes/_suggestions.html",
        {"suggestions": youtube.search_suggestions(q), "q": q},
    )


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
            videos = search_cache.search_with_cache(
                query, lambda: youtube.search_recipe_videos(query)
            )
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
    return render(request, "recipes/_extract_done.html", {"job": job})


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


SORTS = {"recent": "Recently added", "quickest": "Quickest first"}


def _facet_group(name, label, params, sel, counts, *, order=None, labels=None):
    keys = order if order is not None else sorted(counts, key=lambda k: (-counts[k], k))
    options = []
    for value in keys:
        count = counts.get(value, 0)
        if count == 0:
            continue
        options.append({
            "value": value,
            "label": labels[value] if labels else value,
            "count": count,
            "active": value in sel,
            "url": facets.toggle_param(params, name, value),
        })
    return {"name": name, "label": label, "options": options}


@login_required
@onboarding_required
def saved(request):
    user = request.user
    params = request.GET
    cookbook = list(_annotated(Recipe.objects.filter(owner=user), user))
    total = len(cookbook)

    q = params.get("q", "").strip()
    sel = {
        "cuisine": params.getlist("cuisine"),
        "meal": params.getlist("meal"),
        "time": [t for t in params.getlist("time") if t in facets.TIME_BUCKET_KEYS],
        "creator": params.getlist("creator"),
    }
    fav = params.get("fav") == "1"
    sort = params.get("sort") if params.get("sort") in SORTS else "recent"
    view = "list" if params.get("view") == "list" else "grid"

    # Per-value counts over the whole cookbook (documented simplification).
    cuisine_counts = Counter(r.cuisine for r in cookbook if r.cuisine)
    creator_counts = Counter(r.channel_name for r in cookbook if r.channel_name)
    meal_counts = Counter(r.meal_type for r in cookbook if r.meal_type)
    time_counts = Counter(
        b for r in cookbook if (b := facets.time_bucket(r.cook_time_minutes))
    )
    fav_count = sum(1 for r in cookbook if r.is_favorite)

    ql = q.lower()

    def keep(r):
        if ql and ql not in r.title.lower() and ql not in (r.channel_name or "").lower():
            return False
        if sel["cuisine"] and r.cuisine not in sel["cuisine"]:
            return False
        if sel["meal"] and r.meal_type not in sel["meal"]:
            return False
        if sel["time"] and facets.time_bucket(r.cook_time_minutes) not in sel["time"]:
            return False
        if sel["creator"] and r.channel_name not in sel["creator"]:
            return False
        if fav and not r.is_favorite:
            return False
        return True

    results = [r for r in cookbook if keep(r)]
    if sort == "quickest":
        results.sort(key=lambda r: (r.cook_time_minutes is None, r.cook_time_minutes or 0))
    else:
        results.sort(key=lambda r: r.created_at, reverse=True)

    facet_groups = [
        _facet_group("cuisine", "Cuisine", params, sel["cuisine"], cuisine_counts),
        _facet_group("meal", "Meal type", params, sel["meal"], meal_counts,
                     order=facets.MEAL_TYPES, labels=facets.MEAL_LABELS),
        _facet_group("time", "Time", params, sel["time"], time_counts,
                     order=facets.TIME_BUCKET_KEYS,
                     labels={b["key"]: b["label"] for b in facets.TIME_BUCKETS}),
        _facet_group("creator", "Creator", params, sel["creator"], creator_counts),
    ]

    chips = []
    for group in facet_groups:
        for opt in group["options"]:
            if opt["active"]:
                chips.append({"label": opt["label"], "url": opt["url"]})
    if fav:
        chips.append({"label": "Favorites", "url": facets.toggle_param(params, "fav", "1")})

    sort_options = [
        {"value": key, "label": label, "active": key == sort,
         "url": facets.set_param(params, "sort", key)}
        for key, label in SORTS.items()
    ]

    has_filters = bool(q or fav or any(sel.values()))
    # In-progress extractions show as pending cookbook cards in the default
    # (unfiltered) view only: they carry no facet metadata to match against.
    pending_jobs = []
    if not has_filters:
        pending_jobs = list(
            ExtractionJob.objects.filter(owner=user).exclude(
                status__in=[ExtractionJob.Status.DONE, ExtractionJob.Status.FAILED]
            )
        )
        total += len(pending_jobs)

    return render(request, "recipes/cookbook.html", {
        "recipes": results,
        "total": total,
        "shown": len(results),
        "q": q,
        "sort": sort,
        "sort_label": SORTS[sort],
        "sort_options": sort_options,
        "view": view,
        "grid_url": facets.set_param(params, "view", "grid"),
        "list_url": facets.set_param(params, "view", "list"),
        "facet_groups": facet_groups,
        "fav_active": fav,
        "fav_count": fav_count,
        "fav_url": facets.toggle_param(params, "fav", "1"),
        "chips": chips,
        "clear_url": facets.clear_filters(params),
        "has_filters": has_filters,
        "pending_jobs": pending_jobs,
        "preserved_params": [
            (k, v)
            for k, vals in params.lists()
            for v in vals
            if k != "q" and v != ""
        ],
        "reset_url": facets.clear_filters(params, keep=("sort", "view")),
    })


@login_required
@onboarding_required
def cookbook_job_card(request, pk):
    """Poll target for a pending cookbook card. Returns the real recipe card
    once the job is done, a failed placeholder if it failed, else the pending
    placeholder (which keeps polling)."""
    job = get_object_or_404(ExtractionJob, pk=pk, owner=request.user)
    view = "list" if request.GET.get("view") == "list" else "grid"
    if job.status == ExtractionJob.Status.DONE and job.recipe_id:
        recipe = _annotated(
            Recipe.objects.filter(pk=job.recipe_id), request.user
        ).first()
        template = (
            "recipes/_cookbook_row.html" if view == "list"
            else "recipes/_cookbook_card.html"
        )
        return render(request, template, {"recipe": recipe, "view": view})
    template = (
        "recipes/_cookbook_pending_row.html" if view == "list"
        else "recipes/_cookbook_pending_card.html"
    )
    failed = job.status == ExtractionJob.Status.FAILED
    return render(request, template, {"job": job, "view": view, "failed": failed})


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

    steps, starts = [], []
    for i, step in enumerate(recipe.instructions, start=1):
        start = step.get("start") if isinstance(step, dict) else None
        if isinstance(start, bool) or not isinstance(start, int):
            start = None
        text = step.get("text", "") if isinstance(step, dict) else str(step)
        steps.append(
            {"number": i, "text": text, "start": start, "start_display": _mmss(start)}
        )
        starts.append(start)

    rv_data = {"videoId": recipe.youtube_video_id, "steps": starts}
    return render(
        request,
        "recipes/detail.html",
        {"recipe": recipe, "steps": steps, "rv_data": rv_data},
    )


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
    elif request.POST.get("context") == "cookbook":
        if request.POST.get("view") == "list":
            template = "recipes/_cookbook_row.html"
        else:
            template = "recipes/_cookbook_card.html"
    else:
        template = "recipes/_recipe_card.html"
    return render(request, template, {"recipe": recipe, "view": request.POST.get("view", "grid")})


@login_required
@onboarding_required
@require_POST
def delete_recipe(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, owner=request.user)
    recipe.delete()
    resp = HttpResponse(status=204)
    resp["HX-Redirect"] = reverse("saved")
    return resp
