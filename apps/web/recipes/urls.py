from django.urls import path

from . import views

urlpatterns = [
    path("", views.discover, name="discover"),
    path("youtube/search/", views.youtube_search, name="youtube_search"),
    path("youtube/extract/", views.extract_from_captions, name="extract_recipe"),
    path("youtube/suggest/", views.suggest, name="suggest"),
    path("jobs/start/", views.start_job, name="start_job"),
    path("jobs/<int:pk>/status/", views.job_status, name="job_status"),
    path("jobs/<int:pk>/card/", views.cookbook_job_card, name="cookbook_job_card"),
    path("saved/", views.saved, name="saved"),
    path("favorites/", views.favorites, name="favorites"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("recipes/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("recipes/<int:pk>/delete/", views.delete_recipe, name="delete_recipe"),
]
