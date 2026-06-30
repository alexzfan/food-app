"""Best-effort backfill of Recipe.meal_type / Recipe.dietary from tags + title.

Only fills empties (never overwrites). Heuristic keyword matching — values the
LLM didn't classify and whose tags/title give no signal are left blank.
"""
from django.core.management.base import BaseCommand

from recipes.models import Recipe

# First match wins (dict insertion order).
_MEAL_KEYWORDS = {
    "breakfast": "breakfast", "brunch": "breakfast",
    "dessert": "dessert", "cake": "dessert", "cookie": "dessert",
    "side": "side", "appetizer": "side",
    "snack": "snack",
    "lunch": "lunch",
    "dinner": "dinner", "supper": "dinner",
}
_DIET_KEYWORDS = {
    "vegan": "vegan",
    "vegetarian": "vegetarian", "veggie": "vegetarian",
    "gluten-free": "gluten_free", "gluten free": "gluten_free",
    "gluten_free": "gluten_free",
    "gf": "gluten_free",
}


def _haystack(recipe):
    return (" ".join(str(t) for t in recipe.tags) + " " + recipe.title).lower()


def _derive_meal(recipe):
    hay = _haystack(recipe)
    for kw, meal in _MEAL_KEYWORDS.items():
        if kw in hay:
            return meal
    return ""


def _derive_diet(recipe):
    hay = _haystack(recipe)
    out = []
    for kw, diet in _DIET_KEYWORDS.items():
        if kw in hay and diet not in out:
            out.append(diet)
    return out


class Command(BaseCommand):
    help = "Backfill meal_type/dietary on recipes from tags + title (best effort)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report only.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        filled_meal = filled_diet = 0
        for recipe in Recipe.objects.all():
            changed = False
            if not recipe.meal_type:
                meal = _derive_meal(recipe)
                if meal:
                    recipe.meal_type = meal
                    filled_meal += 1
                    changed = True
            if not recipe.dietary:
                diet = _derive_diet(recipe)
                if diet:
                    recipe.dietary = diet
                    filled_diet += 1
                    changed = True
            if changed and not dry:
                recipe.save(update_fields=["meal_type", "dietary"])
        prefix = "[dry-run] " if dry else ""
        self.stdout.write(
            f"{prefix}filled meal_type on {filled_meal}, dietary on {filled_diet} recipes"
        )
