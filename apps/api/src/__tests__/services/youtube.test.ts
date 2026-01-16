import { searchRecipeVideos, getVideoDetails, getVideoTranscript } from "../../services/youtube";
import { mockYouTubeSearchResponse, mockYouTubeVideoResponse, mockTranscript } from "../mocks";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock youtube-transcript
jest.mock("youtube-transcript", () => ({
  YoutubeTranscript: {
    fetchTranscript: jest.fn(),
  },
}));

import { YoutubeTranscript } from "youtube-transcript";

describe("YouTube Service", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("searchRecipeVideos", () => {
    it("should search for recipe videos and return formatted results", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockYouTubeSearchResponse,
      });

      const result = await searchRecipeVideos("pasta", 10);

      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("youtube.googleapis.com/youtube/v3/search")
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("q=pasta+recipe")
      );

      expect(result.videos).toHaveLength(1);
      expect(result.videos[0]).toEqual({
        id: "dQw4w9WgXcQ",
        title: "Easy Garlic Parmesan Pasta Recipe",
        description: "Learn how to make this delicious pasta dish",
        thumbnailUrl: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        channelTitle: "Cooking Channel",
        channelId: "UC123456",
        publishedAt: "2024-01-10T12:00:00Z",
      });
      expect(result.nextPageToken).toBe("NEXT_PAGE_TOKEN");
    });

    it("should include pageToken when provided", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockYouTubeSearchResponse,
      });

      await searchRecipeVideos("pasta", 10, "SOME_TOKEN");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("pageToken=SOME_TOKEN")
      );
    });

    it("should throw error on API failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: async () => "API Error: quota exceeded",
      });

      await expect(searchRecipeVideos("pasta")).rejects.toThrow(
        "YouTube API error: API Error: quota exceeded"
      );
    });
  });

  describe("getVideoDetails", () => {
    it("should fetch video details by ID", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockYouTubeVideoResponse,
      });

      const result = await getVideoDetails("dQw4w9WgXcQ");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("youtube.googleapis.com/youtube/v3/videos")
      );
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("id=dQw4w9WgXcQ")
      );

      expect(result).toEqual({
        id: "dQw4w9WgXcQ",
        title: "Easy Garlic Parmesan Pasta Recipe",
        description: "Learn how to make this delicious pasta dish in under 20 minutes!",
        thumbnailUrl: "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        channelTitle: "Cooking Channel",
        channelId: "UC123456",
        publishedAt: "2024-01-10T12:00:00Z",
      });
    });

    it("should throw error when video not found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ items: [] }),
      });

      await expect(getVideoDetails("invalid-id")).rejects.toThrow(
        "Video not found: invalid-id"
      );
    });

    it("should throw error on API failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: async () => "Not found",
      });

      await expect(getVideoDetails("test")).rejects.toThrow(
        "YouTube API error: Not found"
      );
    });
  });

  describe("getVideoTranscript", () => {
    it("should fetch and concatenate transcript", async () => {
      const mockTranscriptItems = [
        { text: "Today we're making" },
        { text: "an easy pasta dish" },
      ];

      (YoutubeTranscript.fetchTranscript as jest.Mock).mockResolvedValueOnce(
        mockTranscriptItems
      );

      const result = await getVideoTranscript("dQw4w9WgXcQ");

      expect(YoutubeTranscript.fetchTranscript).toHaveBeenCalledWith("dQw4w9WgXcQ");
      expect(result).toBe("Today we're making an easy pasta dish");
    });

    it("should throw error when transcript unavailable", async () => {
      (YoutubeTranscript.fetchTranscript as jest.Mock).mockRejectedValueOnce(
        new Error("Transcript disabled")
      );

      await expect(getVideoTranscript("no-captions")).rejects.toThrow(
        "Failed to fetch transcript for video no-captions"
      );
    });
  });
});
