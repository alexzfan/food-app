from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from . import youtube


@login_required
def discover(request):
    return render(request, "recipes/discover.html")


@login_required
def saved(request):
    # Stub; fully implemented in Task 10.
    return HttpResponse("saved")


@login_required
def favorites(request):
    # Stub; fully implemented in Task 10.
    return HttpResponse("favorites")


@login_required
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
