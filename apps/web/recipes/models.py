from django.conf import settings
from django.db import models


class Recipe(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy"
        MEDIUM = "medium"
        HARD = "hard"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recipes"
    )
    youtube_video_id = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    channel_name = models.CharField(max_length=255, blank=True)
    ingredients = models.JSONField(default=list)   # [{name, amount, unit?, notes?}]
    instructions = models.JSONField(default=list)  # [{step, text, duration?}]
    tags = models.JSONField(default=list)          # [str]
    cuisine = models.CharField(max_length=100, blank=True)
    cook_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    prep_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    servings = models.PositiveIntegerField(null=True, blank=True)
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites"
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="favorited_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "recipe")


class ExtractionJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        TRANSCRIBING = "transcribing"
        EXTRACTING = "extracting"
        DONE = "done"
        FAILED = "failed"

    class Source(models.TextChoices):
        UPLOAD = "upload"
        PASTE_TRANSCRIPT = "paste_transcript"
        PASTE_TEXT = "paste_text"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobs"
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    step_label = models.CharField(max_length=64, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices)
    youtube_video_id = models.CharField(max_length=32, blank=True)
    title = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    recipe = models.ForeignKey(
        Recipe, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
