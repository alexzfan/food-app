import { Router } from "express";
import { authMiddleware } from "../middleware/auth.js";

export const profileRoutes = Router();

// All profile routes require authentication
profileRoutes.use(authMiddleware);

// Get current user profile
profileRoutes.get("/me", async (req, res, next) => {
  try {
    const { data, error } = await req.supabase!
      .from("profiles")
      .select("*")
      .eq("id", req.user!.id)
      .single();

    if (error) {
      throw new Error(`Failed to get profile: ${error.message}`);
    }

    res.json(data);
  } catch (error) {
    next(error);
  }
});

// Update current user profile
profileRoutes.patch("/me", async (req, res, next) => {
  try {
    const { display_name, avatar_url } = req.body;

    const updates: Record<string, string> = {};
    if (display_name !== undefined) updates.display_name = display_name;
    if (avatar_url !== undefined) updates.avatar_url = avatar_url;

    const { data, error } = await req.supabase!
      .from("profiles")
      .update(updates)
      .eq("id", req.user!.id)
      .select()
      .single();

    if (error) {
      throw new Error(`Failed to update profile: ${error.message}`);
    }

    res.json(data);
  } catch (error) {
    next(error);
  }
});
