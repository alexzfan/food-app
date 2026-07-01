from django.conf import settings
from django.db import models

from . import facets, youtube
from .youtube import _format_views, seconds_to_display


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
    creator = models.ForeignKey(
        "Creator", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="recipes",
    )
    ingredients = models.JSONField(default=list)   # [{name, amount, unit?, notes?}]
    instructions = models.JSONField(default=list)  # [{step, text, start?, duration?}]
    tags = models.JSONField(default=list)          # [str]
    cuisine = models.CharField(max_length=100, blank=True)
    meal_type = models.CharField(
        max_length=20, blank=True,
        choices=[(m, facets.MEAL_LABELS[m]) for m in facets.MEAL_TYPES],
    )
    dietary = models.JSONField(default=list)  # subset of facets.DIETARY_TAGS; not surfaced yet
    cook_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    prep_time_minutes = models.PositiveIntegerField(null=True, blank=True)
    servings = models.PositiveIntegerField(null=True, blank=True)
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, blank=True
    )
    transcript = models.TextField(blank=True, default="")  # [seconds]-tagged caption transcript; set for YouTube-caption recipes only
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def cook_time_display(self):
        m = self.cook_time_minutes
        if not m:
            return ""
        if m % 60 == 0:
            return f"{m // 60} HR"
        if m > 60:
            return f"{m // 60} HR {m % 60} MIN"
        return f"{m} MIN"


class Creator(models.Model):
    """Canonical YouTube channel metadata, keyed by channel id.

    Normalized out of Video/Recipe so a channel's avatar is stored once and
    shared across every clip and saved recipe from that creator. Avatars are
    fetched via channels.list during search (see [[youtube]]) and upserted by
    [[search_cache]]; recipes point here through Recipe.creator.
    """
    channel_id = models.CharField(max_length=64, primary_key=True)
    title = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or self.channel_id


class Video(models.Model):
    """Canonical, deduplicated YouTube video metadata for the search cache.

    Display fields (duration/views) are derived, not stored, to stay
    normalized. Rows are upserted on every search that returns the video and
    referenced by SearchResult; see [[search_cache]].
    """
    video_id = models.CharField(max_length=32, primary_key=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    channel_id = models.CharField(max_length=64, blank=True)
    channel_title = models.CharField(max_length=255, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    view_count = models.BigIntegerField(null=True, blank=True)
    has_captions = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["updated_at"])]

    def __str__(self):
        return f"{self.video_id} {self.title}"

    @property
    def duration_display(self):
        return seconds_to_display(self.duration_seconds)

    @property
    def view_count_display(self):
        return _format_views(self.view_count)


class SearchQuery(models.Model):
    """One normalized search string; anchors the TTL for its cached results."""
    query = models.CharField(max_length=255, unique=True)
    fully_enriched = models.BooleanField(default=True)
    fetched_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["fetched_at"])]

    def __str__(self):
        return self.query


class SearchResult(models.Model):
    """Ordered join: which videos a query returned, and in what position."""
    query = models.ForeignKey(
        SearchQuery, on_delete=models.CASCADE, related_name="results"
    )
    video = models.ForeignKey(
        Video, on_delete=models.CASCADE, related_name="appearances"
    )
    rank = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ("query", "video")
        ordering = ["rank"]
        indexes = [models.Index(fields=["query", "rank"])]


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
        YOUTUBE_CAPTIONS = "youtube_captions"

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

    @property
    def thumbnail_url(self):
        """Derived hqdefault thumbnail for the pending cookbook card; "" when
        the job has no source video (e.g. a pasted transcript)."""
        return youtube.thumbnail_url(self.youtube_video_id)
