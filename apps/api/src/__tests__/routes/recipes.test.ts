import request from "supertest";
import { app } from "../../app";
import { mockRecipe, mockYouTubeVideo, mockRecipeSummary, mockTranscript } from "../mocks";

// Mock the services
jest.mock("../../services/supabase", () => ({
  saveRecipe: jest.fn(),
  getRecipeById: jest.fn(),
  getRecipeByVideoId: jest.fn(),
  searchRecipes: jest.fn(),
  getRecipesByTag: jest.fn(),
  getAllRecipes: jest.fn(),
  deleteRecipe: jest.fn(),
}));

jest.mock("../../services/youtube", () => ({
  getVideoDetails: jest.fn(),
  getVideoTranscript: jest.fn(),
}));

jest.mock("../../services/claude", () => ({
  extractRecipeFromTranscript: jest.fn(),
}));

import * as supabaseService from "../../services/supabase";
import * as youtubeService from "../../services/youtube";
import * as claudeService from "../../services/claude";

describe("Recipe Routes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("GET /api/recipes", () => {
    it("should return all recipes with default pagination", async () => {
      (supabaseService.getAllRecipes as jest.Mock).mockResolvedValueOnce([
        mockRecipe,
      ]);

      const response = await request(app).get("/api/recipes");

      expect(response.status).toBe(200);
      expect(response.body).toEqual([mockRecipe]);
      expect(supabaseService.getAllRecipes).toHaveBeenCalledWith(50, 0);
    });

    it("should accept limit and offset parameters", async () => {
      (supabaseService.getAllRecipes as jest.Mock).mockResolvedValueOnce([]);

      await request(app)
        .get("/api/recipes")
        .query({ limit: "10", offset: "20" });

      expect(supabaseService.getAllRecipes).toHaveBeenCalledWith(10, 20);
    });
  });

  describe("GET /api/recipes/search", () => {
    it("should search recipes by query", async () => {
      (supabaseService.searchRecipes as jest.Mock).mockResolvedValueOnce([
        mockRecipe,
      ]);

      const response = await request(app)
        .get("/api/recipes/search")
        .query({ q: "pasta" });

      expect(response.status).toBe(200);
      expect(response.body).toEqual([mockRecipe]);
      expect(supabaseService.searchRecipes).toHaveBeenCalledWith("pasta", 20);
    });

    it("should return 400 when query is missing", async () => {
      const response = await request(app).get("/api/recipes/search");

      expect(response.status).toBe(400);
      expect(response.body).toEqual({
        error: "Query parameter 'q' is required",
      });
    });
  });

  describe("GET /api/recipes/tag/:tag", () => {
    it("should return recipes filtered by tag", async () => {
      (supabaseService.getRecipesByTag as jest.Mock).mockResolvedValueOnce([
        mockRecipe,
      ]);

      const response = await request(app).get("/api/recipes/tag/italian");

      expect(response.status).toBe(200);
      expect(response.body).toEqual([mockRecipe]);
      expect(supabaseService.getRecipesByTag).toHaveBeenCalledWith(
        "italian",
        20
      );
    });
  });

  describe("GET /api/recipes/:id", () => {
    it("should return recipe by ID", async () => {
      (supabaseService.getRecipeById as jest.Mock).mockResolvedValueOnce(
        mockRecipe
      );

      const response = await request(app).get(`/api/recipes/${mockRecipe.id}`);

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockRecipe);
    });

    it("should return 404 when recipe not found", async () => {
      (supabaseService.getRecipeById as jest.Mock).mockResolvedValueOnce(null);

      const response = await request(app).get("/api/recipes/nonexistent-id");

      expect(response.status).toBe(404);
      expect(response.body).toEqual({ error: "Recipe not found" });
    });
  });

  describe("POST /api/recipes/extract", () => {
    it("should extract and save recipe from YouTube video", async () => {
      (supabaseService.getRecipeByVideoId as jest.Mock).mockResolvedValueOnce(
        null
      );
      (youtubeService.getVideoDetails as jest.Mock).mockResolvedValueOnce(
        mockYouTubeVideo
      );
      (youtubeService.getVideoTranscript as jest.Mock).mockResolvedValueOnce(
        mockTranscript
      );
      (claudeService.extractRecipeFromTranscript as jest.Mock).mockResolvedValueOnce(
        mockRecipeSummary
      );
      (supabaseService.saveRecipe as jest.Mock).mockResolvedValueOnce(
        mockRecipe
      );

      const response = await request(app)
        .post("/api/recipes/extract")
        .send({ videoId: "dQw4w9WgXcQ" });

      expect(response.status).toBe(201);
      expect(response.body).toEqual({ recipe: mockRecipe, cached: false });
      expect(youtubeService.getVideoDetails).toHaveBeenCalledWith("dQw4w9WgXcQ");
      expect(youtubeService.getVideoTranscript).toHaveBeenCalledWith(
        "dQw4w9WgXcQ"
      );
      expect(claudeService.extractRecipeFromTranscript).toHaveBeenCalledWith(
        mockTranscript,
        mockYouTubeVideo.title
      );
    });

    it("should return cached recipe if already exists", async () => {
      (supabaseService.getRecipeByVideoId as jest.Mock).mockResolvedValueOnce(
        mockRecipe
      );

      const response = await request(app)
        .post("/api/recipes/extract")
        .send({ videoId: "dQw4w9WgXcQ" });

      expect(response.status).toBe(200);
      expect(response.body).toEqual({ recipe: mockRecipe, cached: true });
      expect(youtubeService.getVideoDetails).not.toHaveBeenCalled();
      expect(claudeService.extractRecipeFromTranscript).not.toHaveBeenCalled();
    });

    it("should return 400 when videoId is missing", async () => {
      const response = await request(app).post("/api/recipes/extract").send({});

      expect(response.status).toBe(400);
      expect(response.body).toEqual({ error: "videoId is required" });
    });

    it("should return 500 on extraction error", async () => {
      (supabaseService.getRecipeByVideoId as jest.Mock).mockResolvedValueOnce(
        null
      );
      (youtubeService.getVideoDetails as jest.Mock).mockRejectedValueOnce(
        new Error("Video not found")
      );

      const response = await request(app)
        .post("/api/recipes/extract")
        .send({ videoId: "invalid" });

      expect(response.status).toBe(500);
      expect(response.body).toEqual({ error: "Video not found" });
    });
  });

  describe("DELETE /api/recipes/:id", () => {
    it("should delete recipe by ID", async () => {
      (supabaseService.deleteRecipe as jest.Mock).mockResolvedValueOnce(
        undefined
      );

      const response = await request(app).delete(
        `/api/recipes/${mockRecipe.id}`
      );

      expect(response.status).toBe(204);
      expect(supabaseService.deleteRecipe).toHaveBeenCalledWith(mockRecipe.id);
    });

    it("should return 500 on delete error", async () => {
      (supabaseService.deleteRecipe as jest.Mock).mockRejectedValueOnce(
        new Error("Delete failed")
      );

      const response = await request(app).delete("/api/recipes/test-id");

      expect(response.status).toBe(500);
      expect(response.body).toEqual({ error: "Delete failed" });
    });
  });
});
