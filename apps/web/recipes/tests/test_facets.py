from django.http import QueryDict

from recipes import facets


def test_normalize_meal_type_known_and_unknown():
    assert facets.normalize_meal_type("Dinner") == "dinner"
    assert facets.normalize_meal_type("  DESSERT ") == "dessert"
    assert facets.normalize_meal_type("brunch") == ""
    assert facets.normalize_meal_type(5) == ""


def test_normalize_dietary_filters_dedupes_and_coerces():
    assert facets.normalize_dietary(["Vegan", "bogus", "vegetarian"]) == ["vegan", "vegetarian"]
    assert facets.normalize_dietary("gluten-free") == ["gluten_free"]
    assert facets.normalize_dietary("Gluten Free") == ["gluten_free"]
    assert facets.normalize_dietary(["vegan", "vegan"]) == ["vegan"]
    assert facets.normalize_dietary(None) == []
    assert facets.normalize_dietary([1, "vegan"]) == ["vegan"]


def test_time_bucket_boundaries():
    assert facets.time_bucket(None) is None
    assert facets.time_bucket(15) == "under15"
    assert facets.time_bucket(16) == "15-30"
    assert facets.time_bucket(30) == "15-30"
    assert facets.time_bucket(60) == "30-60"
    assert facets.time_bucket(61) == "over60"


def test_toggle_param_adds_and_removes_preserving_others():
    q = QueryDict("cuisine=italian&meal=dinner")
    added = QueryDict(facets.toggle_param(q, "cuisine", "french"))
    assert added.getlist("cuisine") == ["italian", "french"]
    assert added.get("meal") == "dinner"
    removed = QueryDict(facets.toggle_param(q, "cuisine", "italian"))
    assert removed.getlist("cuisine") == []
    assert removed.get("meal") == "dinner"


def test_set_param_replaces_single_value():
    q = QueryDict("sort=recent&cuisine=italian")
    out = QueryDict(facets.set_param(q, "sort", "quickest"))
    assert out.get("sort") == "quickest"
    assert out.get("cuisine") == "italian"


def test_clear_filters_keeps_only_view_sort_q():
    q = QueryDict("q=soup&sort=quickest&view=list&cuisine=italian&meal=dinner")
    out = QueryDict(facets.clear_filters(q))
    assert out.get("q") == "soup"
    assert out.get("sort") == "quickest"
    assert out.get("view") == "list"
    assert "cuisine" not in out
    assert "meal" not in out
