import { mockRecipe, mockIngredients, mockInstructions } from "../mocks";

// Mock Supabase client
const mockSelect = jest.fn();
const mockInsert = jest.fn();
const mockDelete = jest.fn();
const mockEq = jest.fn();
const mockOr = jest.fn();
const mockContains = jest.fn();
const mockOrder = jest.fn();
const mockRange = jest.fn();
const mockLimit = jest.fn();
const mockSingle = jest.fn();

const mockFrom = jest.fn(() => ({
  select: mockSelect,
  insert: mockInsert,
  delete: mockDelete,
}));

jest.mock("@supabase/supabase-js", () => ({
  createClient: jest.fn(() => ({
    from: mockFrom,
  })),
}));

// Chain mocks
mockSelect.mockReturnValue({
  eq: mockEq,
  or: mockOr,
  contains: mockContains,
  order: mockOrder,
  single: mockSingle,
});
mockInsert.mockReturnValue({ select: mockSelect });
mockDelete.mockReturnValue({ eq: mockEq });
mockEq.mockReturnValue({ single: mockSingle });
mockOr.mockReturnValue({ limit: mockLimit });
mockContains.mockReturnValue({ limit: mockLimit });
mockOrder.mockReturnValue({ range: mockRange });

import {
  saveRecipe,
  getRecipeById,
  getRecipeByVideoId,
  searchRecipes,
  getRecipesByTag,
  getAllRecipes,
  deleteRecipe,
} from "../../services/supabase";

describe("Supabase Service", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset chain mocks
    mockSelect.mockReturnValue({
      eq: mockEq,
      or: mockOr,
      contains: mockContains,
      order: mockOrder,
      single: mockSingle,
    });
    mockInsert.mockReturnValue({ select: mockSelect });
    mockDelete.mockReturnValue({ eq: mockEq });
    mockEq.mockReturnValue({ single: mockSingle });
    mockOr.mockReturnValue({ limit: mockLimit });
    mockContains.mockReturnValue({ limit: mockLimit });
    mockOrder.mockReturnValue({ range: mockRange });
  });

  describe("saveRecipe", () => {
    it("should save a recipe and return it", async () => {
      mockSingle.mockResolvedValueOnce({ data: mockRecipe, error: null });

      const recipeInput = {
        youtube_video_id: mockRecipe.youtube_video_id,
        title: mockRecipe.title,
        description: mockRecipe.description,
        thumbnail_url: mockRecipe.thumbnail_url,
        channel_name: mockRecipe.channel_name,
        channel_id: mockRecipe.channel_id,
        ingredients: mockIngredients,
        instructions: mockInstructions,
        tags: mockRecipe.tags,
        cuisine: mockRecipe.cuisine,
        cook_time_minutes: mockRecipe.cook_time_minutes,
        prep_time_minutes: mockRecipe.prep_time_minutes,
        servings: mockRecipe.servings,
        difficulty: mockRecipe.difficulty,
      };

      const result = await saveRecipe(recipeInput);

      expect(mockFrom).toHaveBeenCalledWith("recipes");
      expect(mockInsert).toHaveBeenCalledWith(recipeInput);
      expect(result).toEqual(mockRecipe);
    });

    it("should throw error on save failure", async () => {
      mockSingle.mockResolvedValueOnce({
        data: null,
        error: { message: "Duplicate key" },
      });

      await expect(saveRecipe({} as any)).rejects.toThrow(
        "Failed to save recipe: Duplicate key"
      );
    });
  });

  describe("getRecipeById", () => {
    it("should return recipe when found", async () => {
      mockSingle.mockResolvedValueOnce({ data: mockRecipe, error: null });

      const result = await getRecipeById(mockRecipe.id);

      expect(mockFrom).toHaveBeenCalledWith("recipes");
      expect(mockSelect).toHaveBeenCalledWith("*");
      expect(mockEq).toHaveBeenCalledWith("id", mockRecipe.id);
      expect(result).toEqual(mockRecipe);
    });

    it("should return null when recipe not found", async () => {
      mockSingle.mockResolvedValueOnce({
        data: null,
        error: { code: "PGRST116", message: "Not found" },
      });

      const result = await getRecipeById("nonexistent-id");

      expect(result).toBeNull();
    });

    it("should throw error on database failure", async () => {
      mockSingle.mockResolvedValueOnce({
        data: null,
        error: { code: "OTHER", message: "Connection error" },
      });

      await expect(getRecipeById("test-id")).rejects.toThrow(
        "Failed to get recipe: Connection error"
      );
    });
  });

  describe("getRecipeByVideoId", () => {
    it("should return recipe when found by video ID", async () => {
      mockSingle.mockResolvedValueOnce({ data: mockRecipe, error: null });

      const result = await getRecipeByVideoId(mockRecipe.youtube_video_id);

      expect(mockEq).toHaveBeenCalledWith(
        "youtube_video_id",
        mockRecipe.youtube_video_id
      );
      expect(result).toEqual(mockRecipe);
    });

    it("should return null when not found", async () => {
      mockSingle.mockResolvedValueOnce({
        data: null,
        error: { code: "PGRST116", message: "Not found" },
      });

      const result = await getRecipeByVideoId("nonexistent-video");

      expect(result).toBeNull();
    });
  });

  describe("searchRecipes", () => {
    it("should search recipes by title and description", async () => {
      mockLimit.mockResolvedValueOnce({ data: [mockRecipe], error: null });

      const result = await searchRecipes("pasta", 20);

      expect(mockOr).toHaveBeenCalledWith(
        "title.ilike.%pasta%,description.ilike.%pasta%"
      );
      expect(mockLimit).toHaveBeenCalledWith(20);
      expect(result).toEqual([mockRecipe]);
    });

    it("should return empty array when no results", async () => {
      mockLimit.mockResolvedValueOnce({ data: null, error: null });

      const result = await searchRecipes("xyz");

      expect(result).toEqual([]);
    });
  });

  describe("getRecipesByTag", () => {
    it("should filter recipes by tag", async () => {
      mockLimit.mockResolvedValueOnce({ data: [mockRecipe], error: null });

      const result = await getRecipesByTag("italian", 20);

      expect(mockContains).toHaveBeenCalledWith("tags", ["italian"]);
      expect(result).toEqual([mockRecipe]);
    });
  });

  describe("getAllRecipes", () => {
    it("should return paginated recipes", async () => {
      mockRange.mockResolvedValueOnce({ data: [mockRecipe], error: null });

      const result = await getAllRecipes(50, 0);

      expect(mockOrder).toHaveBeenCalledWith("created_at", { ascending: false });
      expect(mockRange).toHaveBeenCalledWith(0, 49);
      expect(result).toEqual([mockRecipe]);
    });
  });

  describe("deleteRecipe", () => {
    it("should delete recipe by ID", async () => {
      mockEq.mockResolvedValueOnce({ error: null });

      await deleteRecipe(mockRecipe.id);

      expect(mockFrom).toHaveBeenCalledWith("recipes");
      expect(mockDelete).toHaveBeenCalled();
      expect(mockEq).toHaveBeenCalledWith("id", mockRecipe.id);
    });

    it("should throw error on delete failure", async () => {
      mockEq.mockResolvedValueOnce({ error: { message: "Delete failed" } });

      await expect(deleteRecipe("test-id")).rejects.toThrow(
        "Failed to delete recipe: Delete failed"
      );
    });
  });
});
