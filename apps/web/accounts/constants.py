# Shared option lists for onboarding preference selection. Single source of truth
# for both templates (render chips) and views (validate submitted values).

CUISINE_OPTIONS = [
    "Italian", "Mexican", "Thai", "Japanese", "Indian",
    "Chinese", "Korean", "French", "Mediterranean", "American",
]

DIET_OPTIONS = [
    "Vegetarian", "Vegan", "Gluten-free", "Dairy-free", "High-protein", "Low-carb",
]

# (minutes, label); 0 == no limit.
COOK_TIME_OPTIONS = [
    (15, "Under 15 min"),
    (30, "Under 30 min"),
    (45, "Under 45 min"),
    (60, "Under 1 hour"),
    (0, "Any length"),
]
