from django.db import migrations


def backfill_thumbnails(apps, schema_editor):
    """Recipes extracted before thumbnail_url was saved have a video id but a
    blank thumbnail. Point them at the deterministic hqdefault URL (matching
    the search API's `high` thumbnail). Recipes with no video id -- pasted
    transcripts -- have nothing to point at and stay blank."""
    Recipe = apps.get_model("recipes", "Recipe")
    to_fix = Recipe.objects.filter(thumbnail_url="").exclude(youtube_video_id="")
    for recipe in to_fix.iterator():
        recipe.thumbnail_url = (
            f"https://i.ytimg.com/vi/{recipe.youtube_video_id}/hqdefault.jpg"
        )
        recipe.save(update_fields=["thumbnail_url"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("recipes", "0005_recipe_meal_type_dietary"),
    ]

    operations = [
        migrations.RunPython(backfill_thumbnails, noop),
    ]
