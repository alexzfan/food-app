from django.contrib import admin

from .models import ExtractionJob, Favorite, Recipe

admin.site.register(Recipe)
admin.site.register(Favorite)
admin.site.register(ExtractionJob)
