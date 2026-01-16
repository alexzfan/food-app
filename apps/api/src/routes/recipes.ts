import { Router } from "express";
import { authMiddleware } from "../middleware/auth.js";
import {
  saveRecipe,
  getRecipeById,
  getRecipeByVideoId,
  searchRecipes,
  getRecipesByTag,
  getAllRecipes,
  deleteRecipe,
} from "../services/supabase.js";
import { getVideoDetails, getVideoTranscript } from "../services/youtube.js";
import { extractRecipeFromTranscript } from "../services/claude.js";

export const recipeRoutes = Router();

// All recipe routes require authentication
recipeRoutes.use(authMiddleware);

// Get all recipes for the authenticated user
recipeRoutes.get("/", async (req, res, next) => {
  try {
    const limit = parseInt(req.query.limit as string) || 50;
    const offset = parseInt(req.query.offset as string) || 0;

    const recipes = await getAllRecipes(
      req.supabase!,
      req.user!.id,
      limit,
      offset
    );

    res.json(recipes);
  } catch (error) {
    next(error);
  }
});

// Search recipes for the authenticated user
recipeRoutes.get("/search", async (req, res, next) => {
  try {
    const query = req.query.q as string;
    const limit = parseInt(req.query.limit as string) || 20;

    if (!query) {
      res.status(400).json({ error: "Query parameter 'q' is required" });
      return;
    }

    const recipes = await searchRecipes(
      req.supabase!,
      req.user!.id,
      query,
      limit
    );

    res.json(recipes);
  } catch (error) {
    next(error);
  }
});

// Get recipes by tag for the authenticated user
recipeRoutes.get("/tag/:tag", async (req, res, next) => {
  try {
    const { tag } = req.params;
    const limit = parseInt(req.query.limit as string) || 20;

    const recipes = await getRecipesByTag(
      req.supabase!,
      req.user!.id,
      tag,
      limit
    );

    res.json(recipes);
  } catch (error) {
    next(error);
  }
});

// Get recipe by ID
recipeRoutes.get("/:id", async (req, res, next) => {
  try {
    const { id } = req.params;

    const recipe = await getRecipeById(req.supabase!, id, req.user!.id);

    if (!recipe) {
      res.status(404).json({ error: "Recipe not found" });
      return;
    }

    res.json(recipe);
  } catch (error) {
    next(error);
  }
});

// Extract and save recipe from YouTube video
recipeRoutes.post("/extract", async (req, res, next) => {
  try {
    const { videoId } = req.body;

    if (!videoId) {
      res.status(400).json({ error: "videoId is required" });
      return;
    }

    // Check if user already has this recipe
    const existing = await getRecipeByVideoId(
      req.supabase!,
      videoId,
      req.user!.id
    );

    if (existing) {
      res.json({ recipe: existing, cached: true });
      return;
    }

    // Get video details and transcript
    const [video, transcript] = await Promise.all([
      getVideoDetails(videoId),
      getVideoTranscript(videoId),
    ]);

    // Extract recipe using Claude
    const recipeSummary = await extractRecipeFromTranscript(
      transcript,
      video.title
    );

    // Save to database with user_id
    const recipe = await saveRecipe(req.supabase!, {
      user_id: req.user!.id,
      youtube_video_id: videoId,
      title: recipeSummary.title,
      description: recipeSummary.description,
      thumbnail_url: video.thumbnailUrl,
      channel_name: video.channelTitle,
      channel_id: video.channelId,
      ingredients: recipeSummary.ingredients,
      instructions: recipeSummary.instructions,
      tags: recipeSummary.tags,
      cuisine: recipeSummary.cuisine,
      cook_time_minutes: recipeSummary.cook_time_minutes,
      prep_time_minutes: recipeSummary.prep_time_minutes,
      servings: recipeSummary.servings,
      difficulty: recipeSummary.difficulty,
    });

    res.status(201).json({ recipe, cached: false });
  } catch (error) {
    next(error);
  }
});

// Delete recipe
recipeRoutes.delete("/:id", async (req, res, next) => {
  try {
    const { id } = req.params;

    await deleteRecipe(req.supabase!, id);

    res.status(204).send();
  } catch (error) {
    next(error);
  }
});
