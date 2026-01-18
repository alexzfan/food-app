import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import {
  searchRecipeVideos,
  getVideoDetails,
} from "../../services/youtube.js";

// Mock fetch globally
const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;

describe("YouTube Service", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("searchRecipeVideos", () => {
    it("should search for recipe videos successfully", async () => {
      const mockResponse = {
        items: [
          {
            id: { videoId: "video123" },
            snippet: {
              title: "Easy Pasta Recipe",
              description: "A simple pasta recipe",
              thumbnails: { high: { url: "https://example.com/thumb.jpg" } },
              channelTitle: "Cooking Channel",
              channelId: "channel123",
              publishedAt: "2024-01-15T12:00:00Z",
            },
          },
          {
            id: { videoId: "video456" },
            snippet: {
              title: "Chicken Stir Fry",
              description: "Quick stir fry recipe",
              thumbnails: { high: { url: "https://example.com/thumb2.jpg" } },
              channelTitle: "Food Network",
              channelId: "channel456",
              publishedAt: "2024-01-14T10:00:00Z",
            },
          },
        ],
        nextPageToken: "NEXT_PAGE_TOKEN",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await searchRecipeVideos("pasta", 10);

      expect(result.videos).toHaveLength(2);
      expect(result.videos[0]).toEqual({
        id: "video123",
        title: "Easy Pasta Recipe",
        description: "A simple pasta recipe",
        thumbnailUrl: "https://example.com/thumb.jpg",
        channelTitle: "Cooking Channel",
        channelId: "channel123",
        publishedAt: "2024-01-15T12:00:00Z",
      });
      expect(result.nextPageToken).toBe("NEXT_PAGE_TOKEN");
    });

    it("should include pageToken in request when provided", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [], nextPageToken: undefined }),
      } as Response);

      await searchRecipeVideos("pasta", 10, "PAGE_TOKEN");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const callUrl = mockFetch.mock.calls[0][0] as string;
      expect(callUrl).toContain("pageToken=PAGE_TOKEN");
    });

    it("should throw error when YouTube API fails", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: async () => "API quota exceeded",
      } as Response);

      await expect(searchRecipeVideos("pasta")).rejects.toThrow(
        "YouTube API error: API quota exceeded"
      );
    });

    it("should append 'recipe' to search query", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);

      await searchRecipeVideos("chicken tikka");

      const callUrl = mockFetch.mock.calls[0][0] as string;
      expect(callUrl).toContain("q=chicken+tikka+recipe");
    });
  });

  describe("getVideoDetails", () => {
    it("should get video details successfully", async () => {
      const mockResponse = {
        items: [
          {
            snippet: {
              title: "Amazing Recipe Video",
              description: "Full description here",
              thumbnails: {
                high: { url: "https://example.com/high.jpg" },
                default: { url: "https://example.com/default.jpg" },
              },
              channelTitle: "Chef's Kitchen",
              channelId: "chef123",
              publishedAt: "2024-01-10T08:00:00Z",
            },
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getVideoDetails("video789");

      expect(result).toEqual({
        id: "video789",
        title: "Amazing Recipe Video",
        description: "Full description here",
        thumbnailUrl: "https://example.com/high.jpg",
        channelTitle: "Chef's Kitchen",
        channelId: "chef123",
        publishedAt: "2024-01-10T08:00:00Z",
      });
    });

    it("should use default thumbnail when high is not available", async () => {
      const mockResponse = {
        items: [
          {
            snippet: {
              title: "Recipe",
              description: "Desc",
              thumbnails: {
                default: { url: "https://example.com/default.jpg" },
              },
              channelTitle: "Channel",
              channelId: "ch1",
              publishedAt: "2024-01-01T00:00:00Z",
            },
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      } as Response);

      const result = await getVideoDetails("vid1");

      expect(result.thumbnailUrl).toBe("https://example.com/default.jpg");
    });

    it("should throw error when video not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);

      await expect(getVideoDetails("nonexistent")).rejects.toThrow(
        "Video not found: nonexistent"
      );
    });

    it("should throw error when API fails", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: async () => "Server error",
      } as Response);

      await expect(getVideoDetails("video123")).rejects.toThrow(
        "YouTube API error: Server error"
      );
    });
  });
});
