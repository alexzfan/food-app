"""Cookbook facet vocabulary, normalization, and querystring helpers.

Single source of truth for the saved-recipe meal-type / dietary vocabularies
and the time-to-cook buckets. Imported by the Recipe model (choices), the
extraction mapping (tasks.py), the backfill command, and the cookbook view.
Pure Python + Django QueryDict — no ORM, no model imports (avoids a circular
import with models).
"""
from urllib.parse import urlencode

MEAL_TYPES = ["breakfast", "lunch", "dinner", "dessert", "side", "snack"]
DIETARY_TAGS = ["vegetarian", "vegan", "gluten_free"]

MEAL_LABELS = {
    "breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner",
    "dessert": "Dessert", "side": "Side", "snack": "Snack",
}
DIET_LABELS = {
    "vegetarian": "Vegetarian", "vegan": "Vegan", "gluten_free": "Gluten-free",
}

# Ordered, non-overlapping cook-time buckets. lo is exclusive, hi inclusive;
# None means unbounded on that side.
TIME_BUCKETS = [
    {"key": "under15", "label": "Under 15", "lo": None, "hi": 15},
    {"key": "15-30", "label": "15–30", "lo": 15, "hi": 30},
    {"key": "30-60", "label": "30–60", "lo": 30, "hi": 60},
    {"key": "over60", "label": "Over 60", "lo": 60, "hi": None},
]
TIME_BUCKET_KEYS = [b["key"] for b in TIME_BUCKETS]


def normalize_meal_type(value):
    """Lowercase/strip a meal type, returning it only if known, else ""."""
    if not isinstance(value, str):
        return ""
    v = value.strip().lower()
    return v if v in MEAL_TYPES else ""


def normalize_dietary(value):
    """Coerce to a deduped, ordered list of known dietary tags.

    Accepts a list/tuple or a single string; lowercases, maps spaces/hyphens to
    underscores, and drops blanks and unknown values.
    """
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        if not isinstance(item, str):
            continue
        v = item.strip().lower().replace("-", "_").replace(" ", "_")
        if v in DIETARY_TAGS and v not in out:
            out.append(v)
    return out


def time_bucket(minutes):
    """Return the bucket key for a cook time in minutes, or None if unknown."""
    if minutes is None:
        return None
    for b in TIME_BUCKETS:
        lo, hi = b["lo"], b["hi"]
        if (lo is None or minutes > lo) and (hi is None or minutes <= hi):
            return b["key"]
    return None


def _as_lists(params):
    """Normalize a QueryDict (or dict-of-lists) to a plain {key: [values]} dict."""
    if hasattr(params, "getlist"):
        return {k: params.getlist(k) for k in params}
    return {k: list(v) for k, v in params.items()}


def _encode(data):
    pairs = []
    for k, vals in data.items():
        for v in vals:
            if v != "":
                pairs.append((k, v))
    return urlencode(pairs)


def toggle_param(params, key, value):
    """Querystring with `value` toggled within multi-value `key`; others kept."""
    data = _as_lists(params)
    current = data.get(key, [])
    if value in current:
        current = [v for v in current if v != value]
    else:
        current = current + [value]
    data[key] = current
    return _encode(data)


def set_param(params, key, value):
    """Querystring with single-value `key` set to `value` (or cleared if empty)."""
    data = _as_lists(params)
    data[key] = [value] if value not in (None, "") else []
    return _encode(data)


def clear_filters(params, keep=("q", "sort", "view")):
    """Querystring keeping only the `keep` params (drops every active filter)."""
    data = {k: v for k, v in _as_lists(params).items() if k in keep}
    return _encode(data)
