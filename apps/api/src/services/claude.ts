import Anthropic from "@anthropic-ai/sdk";
import { env } from "../config/env.js";
import type { RecipeSummary } from "../types/recipe.js";

const anthropic = new Anthropic({
  apiKey: env.ANTHROPIC_API_KEY,
});

const RECIPE_EXTRACTION_PROMPT = `You are a culinary expert that extracts structured recipe information from video transcripts.

Analyze the following transcript from a cooking video and extract the recipe details. Return ONLY valid JSON matching this exact structure:

{
  "title": "Recipe name",
  "description": "Brief 1-2 sentence description of the dish",
  "ingredients": [
    {
      "name": "ingredient name",
      "amount": "quantity as string",
      "unit": "measurement unit (optional)",
      "notes": "any special notes like 'diced' or 'room temperature' (optional)"
    }
  ],
  "instructions": [
    {
      "step": 1,
      "text": "Clear instruction text",
      "duration": "time if mentioned (optional)"
    }
  ],
  "tags": ["relevant", "tags", "like", "cuisine-type", "meal-type", "dietary-info"],
  "cuisine": "cuisine type if identifiable",
  "cook_time_minutes": null or number,
  "prep_time_minutes": null or number,
  "servings": null or number,
  "difficulty": "easy" or "medium" or "hard"
}

Guidelines:
- Extract ALL ingredients mentioned, including sub-recipes or sauces
- Number instructions sequentially and make them clear and actionable
- Include relevant tags for searchability (e.g., "vegetarian", "quick", "italian", "dessert")
- If information is not clearly stated, use null or omit optional fields
- Convert vague measurements to approximate standard measurements when possible
- Keep the description concise but informative

Transcript:
`;

export async function extractRecipeFromTranscript(
  transcript: string,
  videoTitle: string
): Promise<RecipeSummary> {
  const message = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 4096,
    messages: [
      {
        role: "user",
        content: `${RECIPE_EXTRACTION_PROMPT}

Video Title: ${videoTitle}

${transcript}`,
      },
    ],
  });

  const content = message.content[0];
  if (content.type !== "text") {
    throw new Error("Unexpected response type from Claude");
  }

  try {
    // Extract JSON from the response (handle potential markdown code blocks)
    let jsonText = content.text;
    const jsonMatch = jsonText.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) {
      jsonText = jsonMatch[1];
    }

    const recipe: RecipeSummary = JSON.parse(jsonText.trim());
    return recipe;
  } catch (error) {
    throw new Error(`Failed to parse recipe from Claude response: ${error}`);
  }
}
