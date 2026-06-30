import pytest
from django.core.management import call_command

from recipes.models import Recipe


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(email="b@e.com", password="supersecret")


def test_backfill_derives_from_tags(user):
    r = Recipe.objects.create(owner=user, title="Pasta", tags=["Dinner", "Vegan"])
    call_command("backfill_recipe_facets")
    r.refresh_from_db()
    assert r.meal_type == "dinner"
    assert r.dietary == ["vegan"]


def test_backfill_does_not_overwrite_existing(user):
    r = Recipe.objects.create(owner=user, title="Cake", tags=["dessert"], meal_type="snack")
    call_command("backfill_recipe_facets")
    r.refresh_from_db()
    assert r.meal_type == "snack"  # untouched


def test_backfill_dry_run_writes_nothing(user):
    r = Recipe.objects.create(owner=user, title="Pasta", tags=["dinner"])
    call_command("backfill_recipe_facets", "--dry-run")
    r.refresh_from_db()
    assert r.meal_type == ""
