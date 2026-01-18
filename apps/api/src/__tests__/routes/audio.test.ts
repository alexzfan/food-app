import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import request from "supertest";
import express from "express";
import { audioRoutes } from "../../routes/audio.js";

// Mock the auth middleware
jest.mock("../../middleware/auth.js", () => ({
  authMiddleware: jest.fn((req: any, _res: any, next: any) => {
    req.user = { id: "test-user-id", email: "test@example.com", emailVerified: true };
    req.supabase = {};
    next();
  }),
}));

// Mock fetch for audio service calls
const mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;

// Create test app
const app = express();
app.use(express.json());
app.use("/api/audio", audioRoutes);

// Error handler
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  res.status(500).json({ error: err.message });
});

describe("Audio Routes", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe("GET /api/audio/video/:videoId/info", () => {
    it("should return video info from audio service", async () => {
      const mockVideoInfo = {
        video_id: "test-video-123",
        title: "Cooking Tutorial",
        duration: 600,
        channel: "Chef's Kitchen",
        upload_date: "2024-01-15",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockVideoInfo,
      } as Response);

      const response = await request(app).get("/api/audio/video/test-video-123/info");

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockVideoInfo);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/video/test-video-123/info")
      );
    });

    it("should forward error status from audio service", async () => {
      const errorResponse = { error: "Video not found", detail: "Invalid video ID" };

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => errorResponse,
      } as Response);

      const response = await request(app).get("/api/audio/video/invalid-id/info");

      expect(response.status).toBe(404);
      expect(response.body).toEqual(errorResponse);
    });

    it("should handle audio service connection error", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Connection refused"));

      const response = await request(app).get("/api/audio/video/test-video/info");

      expect(response.status).toBe(500);
      expect(response.body.error).toBe("Connection refused");
    });
  });

  describe("GET /api/audio/video/:videoId/transcript", () => {
    it("should return transcript from audio service", async () => {
      const mockTranscript = {
        video_id: "test-video-456",
        title: "Recipe Video",
        duration: 480,
        transcript: "Today we're making pasta. First, boil the water...",
        language: "en",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockTranscript,
      } as Response);

      const response = await request(app).get("/api/audio/video/test-video-456/transcript");

      expect(response.status).toBe(200);
      expect(response.body).toEqual(mockTranscript);
      expect(response.body.transcript).toContain("pasta");
    });

    it("should forward error status from audio service", async () => {
      const errorResponse = { error: "Transcription failed", detail: "Audio too long" };

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => errorResponse,
      } as Response);

      const response = await request(app).get("/api/audio/video/long-video/transcript");

      expect(response.status).toBe(400);
      expect(response.body).toEqual(errorResponse);
    });

    it("should handle json parse error gracefully", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error("Invalid JSON");
        },
      } as unknown as Response);

      const response = await request(app).get("/api/audio/video/broken/transcript");

      expect(response.status).toBe(500);
      expect(response.body.error).toBe("Transcription failed");
    });

    it("should handle audio service timeout", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Request timeout"));

      const response = await request(app).get("/api/audio/video/slow-video/transcript");

      expect(response.status).toBe(500);
      expect(response.body.error).toBe("Request timeout");
    });
  });
});
