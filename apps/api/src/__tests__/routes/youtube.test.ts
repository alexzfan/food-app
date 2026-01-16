import request from "supertest";
import { app } from "../../app";
import { mockYouTubeVideo } from "../mocks";

// Mock the youtube service
jest.mock("../../services/youtube", () => ({
  searchRecipeVideos: jest.fn(),
  getVideoDetails: jest.fn(),
  getVideoTranscript: jest.fn(),
}));

import * as youtubeService from "../../services/youtube";

describe("YouTube Routes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("GET /api/youtube/search", () => {
    it("should return search results", async () => {
      const mockResults = {
        videos: [mockYouTubeVideo],
        nextPageToken: "TOKEN123",
      };

      (youtubeService.searchRecipeVideos as jest.Mock).mockResolvedValueOnce(
        mockResults
      );

      const response = await request(app)
        .get("/api/youtube/search")
        .query({ q: "pasta" });

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockResults);
      expect(youtubeService.searchRecipeVideos).toHaveBeenCalledWith(
        "pasta",
        10,
        undefined
      );
    });

    it("should accept maxResults and pageToken parameters", async () => {
      (youtubeService.searchRecipeVideos as jest.Mock).mockResolvedValueOnce({
        videos: [],
      });

      await request(app)
        .get("/api/youtube/search")
        .query({ q: "chicken", maxResults: "20", pageToken: "ABC123" });

      expect(youtubeService.searchRecipeVideos).toHaveBeenCalledWith(
        "chicken",
        20,
        "ABC123"
      );
    });

    it("should return 400 when query is missing", async () => {
      const response = await request(app).get("/api/youtube/search");

      expect(response.status).toBe(400);
      expect(response.body).toEqual({
        error: "Query parameter 'q' is required",
      });
    });

    it("should return 500 on service error", async () => {
      (youtubeService.searchRecipeVideos as jest.Mock).mockRejectedValueOnce(
        new Error("API quota exceeded")
      );

      const response = await request(app)
        .get("/api/youtube/search")
        .query({ q: "test" });

      expect(response.status).toBe(500);
      expect(response.body).toEqual({ error: "API quota exceeded" });
    });
  });

  describe("GET /api/youtube/video/:videoId", () => {
    it("should return video details", async () => {
      (youtubeService.getVideoDetails as jest.Mock).mockResolvedValueOnce(
        mockYouTubeVideo
      );

      const response = await request(app).get("/api/youtube/video/dQw4w9WgXcQ");

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockYouTubeVideo);
      expect(youtubeService.getVideoDetails).toHaveBeenCalledWith("dQw4w9WgXcQ");
    });

    it("should return 500 when video not found", async () => {
      (youtubeService.getVideoDetails as jest.Mock).mockRejectedValueOnce(
        new Error("Video not found: invalid-id")
      );

      const response = await request(app).get("/api/youtube/video/invalid-id");

      expect(response.status).toBe(500);
      expect(response.body).toEqual({ error: "Video not found: invalid-id" });
    });
  });

  describe("GET /api/youtube/video/:videoId/transcript", () => {
    it("should return video transcript", async () => {
      const mockTranscript = "This is the transcript text";
      (youtubeService.getVideoTranscript as jest.Mock).mockResolvedValueOnce(
        mockTranscript
      );

      const response = await request(app).get(
        "/api/youtube/video/dQw4w9WgXcQ/transcript"
      );

      expect(response.status).toBe(200);
      expect(response.body).toEqual({
        videoId: "dQw4w9WgXcQ",
        transcript: mockTranscript,
      });
    });

    it("should return 500 when transcript unavailable", async () => {
      (youtubeService.getVideoTranscript as jest.Mock).mockRejectedValueOnce(
        new Error("Transcript not available")
      );

      const response = await request(app).get(
        "/api/youtube/video/no-captions/transcript"
      );

      expect(response.status).toBe(500);
      expect(response.body).toEqual({ error: "Transcript not available" });
    });
  });
});
