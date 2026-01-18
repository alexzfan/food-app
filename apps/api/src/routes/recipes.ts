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
import { getVideoDetails } from "../services/youtube.js";

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

// Check if recipe exists for video
recipeRoutes.get("/video/:videoId", async (req, res, next) => {
  try {
    const { videoId } = req.params;

    const existing = await getRecipeByVideoId(
      req.supabase!,
      videoId,
      req.user!.id
    );

    if (existing) {
      res.json({ recipe: existing, exists: true });
    } else {
      res.json({ recipe: null, exists: false });
    }
  } catch (error) {
    next(error);
  }
});

// Save recipe extracted on-device via Gemma 3n
recipeRoutes.post("/", async (req, res, next) => {
  try {
    const {
      videoId,
      title,
      description,
      ingredients,
      instructions,
      tags,
      cuisine,
      cook_time_minutes,
      prep_time_minutes,
      servings,
      difficulty,
    } = req.body;

    if (!videoId || !title) {
      res.status(400).json({ error: "videoId and title are required" });
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

    // Get video details for metadata
    const video = await getVideoDetails(videoId);

    // Save recipe from on-device extraction
    const recipe = await saveRecipe(req.supabase!, {
      user_id: req.user!.id,
      youtube_video_id: videoId,
      title,
      description: description || null,
      thumbnail_url: video.thumbnailUrl,
      channel_name: video.channelTitle,
      channel_id: video.channelId,
      ingredients: ingredients || [],
      instructions: instructions || [],
      tags: tags || [],
      cuisine: cuisine || null,
      cook_time_minutes: cook_time_minutes || null,
      prep_time_minutes: prep_time_minutes || null,
      servings: servings || null,
      difficulty: difficulty || null,
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
