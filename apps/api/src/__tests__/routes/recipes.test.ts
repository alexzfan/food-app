import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import request from "supertest";
import express from "express";
import { recipeRoutes } from "../../routes/recipes.js";

// Mock the auth middleware
jest.mock("../../middleware/auth.js", () => ({
  authMiddleware: jest.fn((req: any, _res: any, next: any) => {
    req.user = { id: "test-user-id", email: "test@example.com", emailVerified: true };
    req.supabase = mockSupabase;
    next();
  }),
}));

// Mock the supabase service
jest.mock("../../services/supabase.js");

// Mock the youtube service
jest.mock("../../services/youtube.js");

import * as supabaseService from "../../services/supabase.js";
import * as youtubeService from "../../services/youtube.js";

const mockSupabase = {};

const mockGetAllRecipes = supabaseService.getAllRecipes as jest.MockedFunction<
  typeof supabaseService.getAllRecipes
>;
const mockSearchRecipes = supabaseService.searchRecipes as jest.MockedFunction<
  typeof supabaseService.searchRecipes
>;
const mockGetRecipeById = supabaseService.getRecipeById as jest.MockedFunction<
  typeof supabaseService.getRecipeById
>;
const mockGetRecipeByVideoId = supabaseService.getRecipeByVideoId as jest.MockedFunction<
  typeof supabaseService.getRecipeByVideoId
>;
const mockGetRecipesByTag = supabaseService.getRecipesByTag as jest.MockedFunction<
  typeof supabaseService.getRecipesByTag
>;
const mockSaveRecipe = supabaseService.saveRecipe as jest.MockedFunction<
  typeof supabaseService.saveRecipe
>;
const mockDeleteRecipe = supabaseService.deleteRecipe as jest.MockedFunction<
  typeof supabaseService.deleteRecipe
>;
const mockGetVideoDetails = youtubeService.getVideoDetails as jest.MockedFunction<
  typeof youtubeService.getVideoDetails
>;

// Create test app
const app = express();
app.use(express.json());
app.use("/api/recipes", recipeRoutes);

// Error handler
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  res.status(500).json({ error: err.message });
});

describe("Recipes Routes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockRecipe = {
    id: "recipe-123",
    user_id: "test-user-id",
    youtube_video_id: "yt-video-123",
    title: "Test Recipe",
    description: "A test recipe",
    thumbnail_url: "https://example.com/thumb.jpg",
    channel_name: "Test Channel",
    channel_id: "channel-123",
    ingredients: [{ name: "flour", amount: "2", unit: "cups" }],
    instructions: [{ step: 1, text: "Mix ingredients" }],
    tags: ["easy", "quick"],
    cuisine: "italian",
    cook_time_minutes: 30,
    prep_time_minutes: 15,
    servings: 4,
    difficulty: "easy" as const,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  };

  describe("GET /api/recipes", () => {
    it("should return all recipes for the user", async () => {
      mockGetAllRecipes.mockResolvedValue([mockRecipe]);

      const response = await request(app).get("/api/recipes");

      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(1);
      expect(response.body[0].title).toBe("Test Recipe");
      expect(mockGetAllRecipes).toHaveBeenCalledWith(
        mockSupabase,
        "test-user-id",
        50,
        0
      );
    });

    it("should respect limit and offset parameters", async () => {
      mockGetAllRecipes.mockResolvedValue([]);

      await request(app).get("/api/recipes?limit=10&offset=20");

      expect(mockGetAllRecipes).toHaveBeenCalledWith(
        mockSupabase,
        "test-user-id",
        10,
        20
      );
    });
  });

  describe("GET /api/recipes/search", () => {
    it("should search recipes by query", async () => {
      mockSearchRecipes.mockResolvedValue([mockRecipe]);

      const response = await request(app).get("/api/recipes/search?q=pasta");

      expect(response.status).toBe(200);
      expect(response.body).toHaveLength(1);
      expect(mockSearchRecipes).toHaveBeenCalledWith(
        mockSupabase,
        "test-user-id",
        "pasta",
        20
      );
    });

    it("should return 400 when query is missing", async () => {
      const response = await request(app).get("/api/recipes/search");

      expect(response.status).toBe(400);
      expect(response.body.error).toBe("Query parameter 'q' is required");
    });
  });

  describe("GET /api/recipes/tag/:tag", () => {
    it("should get recipes by tag", async () => {
      mockGetRecipesByTag.mockResolvedValue([mockRecipe]);

      const response = await request(app).get("/api/recipes/tag/italian");

      expect(response.status).toBe(200);
      expect(mockGetRecipesByTag).toHaveBeenCalledWith(
        mockSupabase,
        "test-user-id",
        "italian",
        20
      );
    });
  });

  describe("GET /api/recipes/:id", () => {
    it("should return recipe by ID", async () => {
      mockGetRecipeById.mockResolvedValue(mockRecipe);

      const response = await request(app).get("/api/recipes/recipe-123");

      expect(response.status).toBe(200);
      expect(response.body.id).toBe("recipe-123");
    });

    it("should return 404 when recipe not found", async () => {
      mockGetRecipeById.mockResolvedValue(null);

      const response = await request(app).get("/api/recipes/nonexistent");

      expect(response.status).toBe(404);
      expect(response.body.error).toBe("Recipe not found");
    });
  });

  describe("GET /api/recipes/video/:videoId", () => {
    it("should return exists:true when recipe exists for video", async () => {
      mockGetRecipeByVideoId.mockResolvedValue(mockRecipe);

      const response = await request(app).get("/api/recipes/video/yt-video-123");

      expect(response.status).toBe(200);
      expect(response.body.exists).toBe(true);
      expect(response.body.recipe.id).toBe("recipe-123");
    });

    it("should return exists:false when no recipe for video", async () => {
      mockGetRecipeByVideoId.mockResolvedValue(null);

      const response = await request(app).get("/api/recipes/video/new-video");

      expect(response.status).toBe(200);
      expect(response.body.exists).toBe(false);
      expect(response.body.recipe).toBeNull();
    });
  });

  describe("POST /api/recipes", () => {
    const newRecipeData = {
      videoId: "new-video-id",
      title: "New Recipe",
      description: "A new recipe",
      ingredients: [{ name: "salt", amount: "1", unit: "tsp" }],
      instructions: [{ step: 1, text: "Add salt" }],
      tags: ["simple"],
      cuisine: "american",
    };

    it("should create a new recipe", async () => {
      mockGetRecipeByVideoId.mockResolvedValue(null);
      mockGetVideoDetails.mockResolvedValue({
        id: "new-video-id",
        title: "Video Title",
        description: "Video description",
        thumbnailUrl: "https://example.com/video-thumb.jpg",
        channelTitle: "Video Channel",
        channelId: "video-channel-id",
        publishedAt: "2024-01-01T00:00:00Z",
      });
      mockSaveRecipe.mockResolvedValue({ ...mockRecipe, ...newRecipeData });

      const response = await request(app)
        .post("/api/recipes")
        .send(newRecipeData);

      expect(response.status).toBe(201);
      expect(response.body.cached).toBe(false);
      expect(mockSaveRecipe).toHaveBeenCalled();
    });

    it("should return cached recipe when already exists", async () => {
      mockGetRecipeByVideoId.mockResolvedValue(mockRecipe);

      const response = await request(app)
        .post("/api/recipes")
        .send(newRecipeData);

      expect(response.status).toBe(200);
      expect(response.body.cached).toBe(true);
      expect(response.body.recipe.id).toBe("recipe-123");
      expect(mockSaveRecipe).not.toHaveBeenCalled();
    });

    it("should return 400 when videoId is missing", async () => {
      const response = await request(app)
        .post("/api/recipes")
        .send({ title: "Recipe without videoId" });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe("videoId and title are required");
    });

    it("should return 400 when title is missing", async () => {
      const response = await request(app)
        .post("/api/recipes")
        .send({ videoId: "video-123" });

      expect(response.status).toBe(400);
      expect(response.body.error).toBe("videoId and title are required");
    });
  });

  describe("DELETE /api/recipes/:id", () => {
    it("should delete recipe and return 204", async () => {
      mockDeleteRecipe.mockResolvedValue(undefined);

      const response = await request(app).delete("/api/recipes/recipe-123");

      expect(response.status).toBe(204);
      expect(mockDeleteRecipe).toHaveBeenCalledWith(mockSupabase, "recipe-123");
    });
  });
});
