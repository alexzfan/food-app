from django.db import migrations


def backfill_creators(apps, schema_editor):
    """Link recipes saved before the Creator model existed to a Creator, using
    the channel on their cached Video. Avatars fill in on the next search of
    that channel; recipes whose cache row is gone stay unlinked."""
    Recipe = apps.get_model("recipes", "Recipe")
    Video = apps.get_model("recipes", "Video")
    Creator = apps.get_model("recipes", "Creator")

    videos = {
        v.video_id: v
        for v in Video.objects.exclude(channel_id="")
    }
    unlinked = Recipe.objects.filter(creator__isnull=True).exclude(youtube_video_id="")
    for recipe in unlinked.iterator():
        video = videos.get(recipe.youtube_video_id)
        if not video:
            continue
        creator, _ = Creator.objects.get_or_create(
            channel_id=video.channel_id,
            defaults={"title": video.channel_title},
        )
        recipe.creator = creator
        recipe.save(update_fields=["creator"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0007_creator_recipe_creator"),
    ]

    operations = [
        migrations.RunPython(backfill_creators, noop),
    ]
