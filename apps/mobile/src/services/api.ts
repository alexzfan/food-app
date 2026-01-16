import { supabase } from "../lib/supabase";
import type { Recipe, YouTubeSearchResult, YouTubeVideo } from "../types";

// Update this to your actual API URL
const API_BASE_URL = __DEV__
  ? "http://localhost:3000/api"
  : "https://your-production-api.com/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function getAuthHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    throw new ApiError(401, "Not authenticated");
  }

  return {
    Authorization: `Bearer ${session.access_token}`,
  };
}

async function request<T>(
  endpoint: string,
  options?: RequestInit,
  requireAuth = true
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options?.headers,
  };

  if (requireAuth) {
    const authHeaders = await getAuthHeaders();
    Object.assign(headers, authHeaders);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "Request failed" }));
    throw new ApiError(response.status, error.error || "Request failed");
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================
// YouTube endpoints (no auth required for search)
// ============================================

export async function searchYouTubeVideos(
  query: string,
  maxResults = 10,
  pageToken?: string
): Promise<YouTubeSearchResult> {
  const params = new URLSearchParams({ q: query, maxResults: maxResults.toString() });
  if (pageToken) params.set("pageToken", pageToken);

  // YouTube search doesn't require auth
  return request<YouTubeSearchResult>(`/youtube/search?${params}`, undefined, false);
}

export async function getYouTubeVideo(videoId: string): Promise<YouTubeVideo> {
  return request<YouTubeVideo>(`/youtube/video/${videoId}`, undefined, false);
}

export async function getVideoTranscript(
  videoId: string
): Promise<{ videoId: string; transcript: string }> {
  return request(`/youtube/video/${videoId}/transcript`, undefined, false);
}

// ============================================
// Recipe endpoints (auth required)
// ============================================

export async function getAllRecipes(limit = 50, offset = 0): Promise<Recipe[]> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  return request<Recipe[]>(`/recipes?${params}`);
}

export async function searchRecipes(query: string, limit = 20): Promise<Recipe[]> {
  const params = new URLSearchParams({ q: query, limit: limit.toString() });
  return request<Recipe[]>(`/recipes/search?${params}`);
}

export async function getRecipesByTag(tag: string, limit = 20): Promise<Recipe[]> {
  const params = new URLSearchParams({ limit: limit.toString() });
  return request<Recipe[]>(`/recipes/tag/${tag}?${params}`);
}

export async function getRecipeById(id: string): Promise<Recipe> {
  return request<Recipe>(`/recipes/${id}`);
}

export async function extractRecipeFromVideo(
  videoId: string
): Promise<{ recipe: Recipe; cached: boolean }> {
  return request<{ recipe: Recipe; cached: boolean }>("/recipes/extract", {
    method: "POST",
    body: JSON.stringify({ videoId }),
  });
}

export async function deleteRecipe(id: string): Promise<void> {
  return request(`/recipes/${id}`, { method: "DELETE" });
}

// ============================================
// Favorites endpoints (auth required)
// ============================================

export async function getFavorites(limit = 50, offset = 0): Promise<Recipe[]> {
  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });
  return request<Recipe[]>(`/favorites?${params}`);
}

export async function addFavorite(recipeId: string): Promise<void> {
  return request(`/favorites/${recipeId}`, { method: "POST" });
}

export async function removeFavorite(recipeId: string): Promise<void> {
  return request(`/favorites/${recipeId}`, { method: "DELETE" });
}

// ============================================
// Profile endpoints (auth required)
// ============================================

export interface UserProfile {
  id: string;
  email?: string;
  display_name?: string;
  avatar_url?: string;
  created_at: string;
  updated_at: string;
}

export async function getProfile(): Promise<UserProfile> {
  return request<UserProfile>("/profile/me");
}

export async function updateProfile(data: {
  display_name?: string;
  avatar_url?: string;
}): Promise<UserProfile> {
  return request<UserProfile>("/profile/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ============================================
// Auth/Verification endpoints
// ============================================

export interface VerificationStatus {
  verified: boolean;
  email?: string;
  confirmedAt?: string;
}

export async function getVerificationStatus(): Promise<VerificationStatus> {
  return request<VerificationStatus>("/auth/verification-status");
}

export async function resendVerificationEmail(email: string): Promise<{ message: string }> {
  return request<{ message: string }>(
    "/auth/resend-verification",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
    false // No auth required
  );
}
