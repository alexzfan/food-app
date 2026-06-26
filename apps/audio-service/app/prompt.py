RECIPE_EXTRACTION_PROMPT = """You are a culinary expert that extracts structured recipe information from video transcripts.

Analyze the following transcript from a cooking video and extract the recipe details. Return ONLY valid JSON matching this exact structure:

{
  "title": "Recipe name",
  "description": "Brief 1-2 sentence description of the dish",
  "ingredients": [
    {"name": "ingredient name", "amount": "quantity as string", "unit": "measurement unit (optional)", "notes": "notes like 'diced' (optional)"}
  ],
  "instructions": [
    {"step": 1, "text": "Clear instruction text", "duration": "time if mentioned (optional)"}
  ],
  "tags": ["relevant", "tags"],
  "cuisine": "cuisine type if identifiable",
  "cook_time_minutes": null,
  "prep_time_minutes": null,
  "servings": null,
  "difficulty": "easy"
}

Guidelines:
- Extract ALL ingredients mentioned
- Number instructions sequentially
- Use null for unknown values
- Return ONLY the JSON, no other text

Transcript:
"""


def build_prompt(transcript: str, title: str | None) -> str:
    if title:
        return f"{RECIPE_EXTRACTION_PROMPT}\n\nVideo Title: {title}\n\n{transcript}"
    return f"{RECIPE_EXTRACTION_PROMPT}\n\n{transcript}"
