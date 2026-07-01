import importlib

from django.apps import apps as django_apps

from recipes.models import Creator, Recipe, Video

BACKFILL = importlib.import_module(
    "recipes.migrations.0006_backfill_recipe_thumbnail_url"
)
BACKFILL_CREATORS = importlib.import_module(
    "recipes.migrations.0008_backfill_recipe_creator"
)


def test_backfill_sets_derived_thumbnail_for_video_recipes(db, django_user_model):
    user = django_user_model.objects.create_user(
        email="m@e.com", password="supersecret"
    )
    # Legacy rows: a real extracted recipe (video id, blank thumbnail) and a
    # pasted-transcript recipe (no video id).
    with_video = Recipe.objects.create(
        owner=user, title="Has video", youtube_video_id="abc123"
    )
    no_video = Recipe.objects.create(owner=user, title="No video")
    already = Recipe.objects.create(
        owner=user, title="Already set", youtube_video_id="zzz999",
        thumbnail_url="https://i.ytimg.com/vi/zzz999/mqdefault.jpg",
    )

    BACKFILL.backfill_thumbnails(django_apps, None)

    with_video.refresh_from_db()
    no_video.refresh_from_db()
    already.refresh_from_db()
    assert with_video.thumbnail_url == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    assert no_video.thumbnail_url == ""  # nothing to point at
    # existing thumbnail left untouched
    assert already.thumbnail_url == "https://i.ytimg.com/vi/zzz999/mqdefault.jpg"


def test_backfill_creators_links_from_cached_video(db, django_user_model):
    user = django_user_model.objects.create_user(
        email="c@e.com", password="supersecret"
    )
    Video.objects.create(
        video_id="abc123", title="Pasta vid", channel_id="ch1", channel_title="Chef"
    )
    with_video = Recipe.objects.create(
        owner=user, title="Has video", youtube_video_id="abc123"
    )
    no_cache = Recipe.objects.create(
        owner=user, title="No cached video", youtube_video_id="gone999"
    )
    assert with_video.creator_id is None

    BACKFILL_CREATORS.backfill_creators(django_apps, None)

    with_video.refresh_from_db()
    no_cache.refresh_from_db()
    assert with_video.creator_id == "ch1"
    assert Creator.objects.get(channel_id="ch1").title == "Chef"
    assert no_cache.creator_id is None  # no cached video to resolve the channel
