RECIPE_EXTRACTION_PROMPT = """You are a culinary expert that extracts structured recipe information from video transcripts.

Analyze the following transcript from a cooking video and extract the recipe details. Return ONLY valid JSON matching this exact structure:

{
  "title": "Recipe name",
  "description": "Brief 1-2 sentence description of the dish",
  "ingredients": [
    {"name": "ingredient name", "amount": "quantity as string", "unit": "measurement unit (optional)", "notes": "notes like 'diced' (optional)"}
  ],
  "instructions": [
    {"step": 1, "text": "Clear instruction text", "start": 12, "duration": "time if mentioned (optional)"}
  ],
  "tags": ["relevant", "tags"],
  "meal_type": "one of: breakfast, lunch, dinner, dessert, side, snack (or \"\" if unclear)",
  "dietary": ["any of: vegetarian, vegan, gluten_free that clearly apply; [] if none"],
  "cuisine": "cuisine type if identifiable",
  "cook_time_minutes": null,
  "prep_time_minutes": null,
  "servings": null,
  "difficulty": "easy"
}

Guidelines:
- Extract ALL ingredients mentioned
- Number instructions sequentially
- Each transcript line may be prefixed with its start time in seconds in square brackets, e.g. "[12] add the garlic". Set each instruction's "start" to the integer seconds tag of the line where that step begins. Use null when the transcript has no timestamps or the moment is unclear.
- Use null for unknown values
- "meal_type": the single best-fit meal category from the list above, or "" if unclear.
- "dietary": only tags clearly supported by the recipe. Use "vegan" only when no animal
  products at all; "vegetarian" when no meat or fish; "gluten_free" when no gluten
  ingredients. Use [] when none clearly apply.
- Return ONLY the JSON, no other text

Transcript:
"""


def build_prompt(transcript: str, title: str | None) -> str:
    if title:
        return f"{RECIPE_EXTRACTION_PROMPT}\n\nVideo Title: {title}\n\n{transcript}"
    return f"{RECIPE_EXTRACTION_PROMPT}\n\n{transcript}"
