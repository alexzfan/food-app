import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { env } from "../config/env.js";
import type { Recipe, Favorite } from "../types/recipe.js";

// Admin client for operations that don't need user context
export const supabaseAdmin = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY);

// Type for recipe input (without auto-generated fields)
type RecipeInput = Omit<Recipe, "id" | "created_at" | "updated_at" | "is_favorite">;

// ============================================
// RECIPE OPERATIONS
// ============================================

export async function saveRecipe(
  supabase: SupabaseClient,
  recipe: RecipeInput
): Promise<Recipe> {
  const { data, error } = await supabase
    .from("recipes")
    .insert(recipe)
    .select()
    .single();

  if (error) {
    throw new Error(`Failed to save recipe: ${error.message}`);
  }

  return data;
}

export async function getRecipeById(
  supabase: SupabaseClient,
  id: string,
  userId: string
): Promise<Recipe | null> {
  // Get recipe with favorite status
  const { data: recipe, error } = await supabase
    .from("recipes")
    .select("*")
    .eq("id", id)
    .single();

  if (error) {
    if (error.code === "PGRST116") return null;
    throw new Error(`Failed to get recipe: ${error.message}`);
  }

  // Check if favorited
  const { data: favorite } = await supabase
    .from("favorites")
    .select("id")
    .eq("recipe_id", id)
    .eq("user_id", userId)
    .single();

  return { ...recipe, is_favorite: !!favorite };
}

export async function getRecipeByVideoId(
  supabase: SupabaseClient,
  videoId: string,
  userId: string
): Promise<Recipe | null> {
  const { data, error } = await supabase
    .from("recipes")
    .select("*")
    .eq("youtube_video_id", videoId)
    .eq("user_id", userId)
    .single();

  if (error) {
    if (error.code === "PGRST116") return null;
    throw new Error(`Failed to get recipe: ${error.message}`);
  }

  return data;
}

export async function searchRecipes(
  supabase: SupabaseClient,
  userId: string,
  query: string,
  limit = 20
): Promise<Recipe[]> {
  const { data, error } = await supabase
    .from("recipes")
    .select("*")
    .eq("user_id", userId)
    .or(`title.ilike.%${query}%,description.ilike.%${query}%`)
    .limit(limit);

  if (error) {
    throw new Error(`Failed to search recipes: ${error.message}`);
  }

  return await attachFavoriteStatus(supabase, userId, data || []);
}

export async function getRecipesByTag(
  supabase: SupabaseClient,
  userId: string,
  tag: string,
  limit = 20
): Promise<Recipe[]> {
  const { data, error } = await supabase
    .from("recipes")
    .select("*")
    .eq("user_id", userId)
    .contains("tags", [tag])
    .limit(limit);

  if (error) {
    throw new Error(`Failed to get recipes by tag: ${error.message}`);
  }

  return await attachFavoriteStatus(supabase, userId, data || []);
}

export async function getAllRecipes(
  supabase: SupabaseClient,
  userId: string,
  limit = 50,
  offset = 0
): Promise<Recipe[]> {
  const { data, error } = await supabase
    .from("recipes")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) {
    throw new Error(`Failed to get recipes: ${error.message}`);
  }

  return await attachFavoriteStatus(supabase, userId, data || []);
}

export async function deleteRecipe(
  supabase: SupabaseClient,
  id: string
): Promise<void> {
  const { error } = await supabase
    .from("recipes")
    .delete()
    .eq("id", id);

  if (error) {
    throw new Error(`Failed to delete recipe: ${error.message}`);
  }
}

// ============================================
// FAVORITES OPERATIONS
// ============================================

export async function addFavorite(
  supabase: SupabaseClient,
  userId: string,
  recipeId: string
): Promise<Favorite> {
  const { data, error } = await supabase
    .from("favorites")
    .insert({ user_id: userId, recipe_id: recipeId })
    .select()
    .single();

  if (error) {
    if (error.code === "23505") {
      throw new Error("Recipe is already in favorites");
    }
    throw new Error(`Failed to add favorite: ${error.message}`);
  }

  return data;
}

export async function removeFavorite(
  supabase: SupabaseClient,
  userId: string,
  recipeId: string
): Promise<void> {
  const { error } = await supabase
    .from("favorites")
    .delete()
    .eq("user_id", userId)
    .eq("recipe_id", recipeId);

  if (error) {
    throw new Error(`Failed to remove favorite: ${error.message}`);
  }
}

export async function getFavorites(
  supabase: SupabaseClient,
  userId: string,
  limit = 50,
  offset = 0
): Promise<Recipe[]> {
  const { data, error } = await supabase
    .from("favorites")
    .select(`
      recipe_id,
      created_at,
      recipes (*)
    `)
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (error) {
    throw new Error(`Failed to get favorites: ${error.message}`);
  }

  // Extract recipes from join and mark as favorite
  return (data || []).map((fav: any) => ({
    ...fav.recipes,
    is_favorite: true,
  }));
}

export async function isFavorite(
  supabase: SupabaseClient,
  userId: string,
  recipeId: string
): Promise<boolean> {
  const { data } = await supabase
    .from("favorites")
    .select("id")
    .eq("user_id", userId)
    .eq("recipe_id", recipeId)
    .single();

  return !!data;
}

// Helper to attach favorite status to recipes
async function attachFavoriteStatus(
  supabase: SupabaseClient,
  userId: string,
  recipes: Recipe[]
): Promise<Recipe[]> {
  if (recipes.length === 0) return recipes;

  const recipeIds = recipes.map((r) => r.id);

  const { data: favorites } = await supabase
    .from("favorites")
    .select("recipe_id")
    .eq("user_id", userId)
    .in("recipe_id", recipeIds);

  const favoriteSet = new Set((favorites || []).map((f) => f.recipe_id));

  return recipes.map((recipe) => ({
    ...recipe,
    is_favorite: favoriteSet.has(recipe.id),
  }));
}
