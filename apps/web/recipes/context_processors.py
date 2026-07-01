from .models import ExtractionJob, Recipe


def cookbook_badge(request):
    """Live cookbook size for the Saved nav badge: saved recipes plus
    in-progress extractions (each renders as a pending cookbook card)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    recipes = Recipe.objects.filter(owner=user).count()
    active = (
        ExtractionJob.objects.filter(owner=user)
        .exclude(status__in=[ExtractionJob.Status.DONE, ExtractionJob.Status.FAILED])
        .count()
    )
    return {"cookbook_count": recipes + active}
