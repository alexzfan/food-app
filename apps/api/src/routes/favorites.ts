import { Router } from "express";
import { authMiddleware } from "../middleware/auth.js";
import {
  getFavorites,
  addFavorite,
  removeFavorite,
} from "../services/supabase.js";

export const favoritesRoutes = Router();

// All favorites routes require authentication
favoritesRoutes.use(authMiddleware);

// Get all favorites
favoritesRoutes.get("/", async (req, res, next) => {
  try {
    const limit = parseInt(req.query.limit as string) || 50;
    const offset = parseInt(req.query.offset as string) || 0;

    const favorites = await getFavorites(
      req.supabase!,
      req.user!.id,
      limit,
      offset
    );

    res.json(favorites);
  } catch (error) {
    next(error);
  }
});

// Add to favorites
favoritesRoutes.post("/:recipeId", async (req, res, next) => {
  try {
    const { recipeId } = req.params;

    const favorite = await addFavorite(req.supabase!, req.user!.id, recipeId);

    res.status(201).json(favorite);
  } catch (error) {
    next(error);
  }
});

// Remove from favorites
favoritesRoutes.delete("/:recipeId", async (req, res, next) => {
  try {
    const { recipeId } = req.params;

    await removeFavorite(req.supabase!, req.user!.id, recipeId);

    res.status(204).send();
  } catch (error) {
    next(error);
  }
});
