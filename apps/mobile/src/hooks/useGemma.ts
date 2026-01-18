/**
 * Gemma On-Device LLM Hook
 *
 * Uses expo-llm-mediapipe to run Gemma locally on the device
 * for recipe extraction from transcript text.
 *
 * Note: expo-llm-mediapipe is still evolving. This implementation
 * uses the documented API and adds state management for UX.
 */

import { useLLM } from "expo-llm-mediapipe";
import { useState, useCallback, useEffect } from "react";
import type { RecipeSummary } from "../types";

// Gemma model configuration
// Using Gemma 2B quantized for mobile
const MODEL_CONFIG = {
  modelName: "gemma-1.1-2b-it-cpu-int4.bin",
  modelUrl:
    "https://huggingface.co/prabhat-ai/gemma-1.1-2b-it-tflite/resolve/main/gemma-1.1-2b-it-cpu-int4.bin",
  maxTokens: 2048,
  temperature: 0.7,
  topK: 40,
  randomSeed: 42,
};

// Recipe extraction prompt
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
  "cook_time_minutes": null,
  "prep_time_minutes": null,
  "servings": null,
  "difficulty": "easy"
}

Guidelines:
- Extract ALL ingredients mentioned
- Number instructions sequentially
- Include relevant tags for searchability
- Use null for unknown values
- Return ONLY the JSON, no other text

Transcript:
`;

interface UseGemmaRecipeResult {
  // State
  isModelLoaded: boolean;
  isDownloading: boolean;
  isExtracting: boolean;
  downloadProgress: number;
  error: string | null;

  // Actions
  downloadModel: () => Promise<void>;
  extractRecipe: (
    transcript: string,
    videoTitle?: string
  ) => Promise<RecipeSummary>;
}

export function useGemmaRecipe(): UseGemmaRecipeResult {
  // Local state for tracking operations
  const [isDownloading, setIsDownloading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Use the expo-llm-mediapipe hook
  const llm = useLLM({
    modelName: MODEL_CONFIG.modelName,
    modelUrl: MODEL_CONFIG.modelUrl,
    maxTokens: MODEL_CONFIG.maxTokens,
    temperature: MODEL_CONFIG.temperature,
    topK: MODEL_CONFIG.topK,
    randomSeed: MODEL_CONFIG.randomSeed,
  });

  // Check for library-provided download progress if available
  useEffect(() => {
    // Some versions of the library expose downloadProgress
    if ("downloadProgress" in llm && typeof llm.downloadProgress === "number") {
      setDownloadProgress(llm.downloadProgress);
    }
  }, [(llm as any).downloadProgress]);

  const downloadModel = useCallback(async () => {
    setIsDownloading(true);
    setDownloadProgress(0);
    setError(null);

    try {
      // Simulate progress since the library may not expose it
      const progressInterval = setInterval(() => {
        setDownloadProgress((prev) => Math.min(prev + 0.05, 0.9));
      }, 500);

      await llm.downloadModel();
      clearInterval(progressInterval);
      setDownloadProgress(0.95);

      await llm.loadModel();
      setDownloadProgress(1);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Download failed";
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setIsDownloading(false);
    }
  }, [llm]);

  const extractRecipe = useCallback(
    async (
      transcript: string,
      videoTitle?: string
    ): Promise<RecipeSummary> => {
      if (!llm.isLoaded) {
        throw new Error("Model not loaded. Call downloadModel() first.");
      }

      setIsExtracting(true);
      setError(null);

      try {
        // Build prompt with video title for context
        const prompt = videoTitle
          ? `${RECIPE_EXTRACTION_PROMPT}\n\nVideo Title: ${videoTitle}\n\n${transcript}`
          : `${RECIPE_EXTRACTION_PROMPT}\n\n${transcript}`;

        // Generate response using on-device model
        const response = await llm.generateResponse(prompt);

        // Parse JSON from response
        const recipe = parseRecipeResponse(response);
        return recipe;
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Extraction failed";
        setError(errorMessage);
        throw new Error(errorMessage);
      } finally {
        setIsExtracting(false);
      }
    },
    [llm]
  );

  return {
    isModelLoaded: llm.isLoaded ?? false,
    isDownloading,
    isExtracting,
    downloadProgress,
    error,
    downloadModel,
    extractRecipe,
  };
}

/**
 * Parse recipe JSON from LLM response
 */
function parseRecipeResponse(response: string): RecipeSummary {
  // Clean up response
  let jsonText = response.trim();

  // Handle markdown code blocks
  const jsonMatch = jsonText.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (jsonMatch) {
    jsonText = jsonMatch[1];
  }

  // Try to find JSON object
  const objectMatch = jsonText.match(/\{[\s\S]*\}/);
  if (objectMatch) {
    jsonText = objectMatch[0];
  }

  try {
    const recipe: RecipeSummary = JSON.parse(jsonText);

    // Validate required fields
    if (!recipe.title) {
      throw new Error("Missing required field: title");
    }

    // Ensure arrays exist with defaults
    recipe.ingredients = recipe.ingredients || [];
    recipe.instructions = recipe.instructions || [];
    recipe.tags = recipe.tags || [];

    return recipe;
  } catch (err) {
    console.error("Failed to parse recipe JSON:", response);
    throw new Error(`Failed to parse recipe: ${err}`);
  }
}
