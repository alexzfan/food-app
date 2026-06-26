from django.urls import path

from . import views

urlpatterns = [
    path("", views.discover, name="discover"),
    path("youtube/search/", views.youtube_search, name="youtube_search"),
    # Stub routes for nav links; fully implemented in Task 10.
    path("saved/", views.saved, name="saved"),
    path("favorites/", views.favorites, name="favorites"),
]
