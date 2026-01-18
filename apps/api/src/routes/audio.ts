import { Router } from "express";
import { authMiddleware } from "../middleware/auth.js";
import { env } from "../config/env.js";

export const audioRoutes = Router();

// All audio routes require authentication
audioRoutes.use(authMiddleware);

// Get video info (proxy to audio service)
audioRoutes.get("/video/:videoId/info", async (req, res, next) => {
  try {
    const { videoId } = req.params;

    const response = await fetch(
      `${env.AUDIO_SERVICE_URL}/video/${videoId}/info`
    );

    if (!response.ok) {
      const error = await response.json();
      res.status(response.status).json(error);
      return;
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// Get video transcript (proxy to audio service - includes Whisper transcription)
audioRoutes.get("/video/:videoId/transcript", async (req, res, next) => {
  try {
    const { videoId } = req.params;

    const response = await fetch(
      `${env.AUDIO_SERVICE_URL}/video/${videoId}/transcript`
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: "Transcription failed" }));
      res.status(response.status).json(error);
      return;
    }

    const data = await response.json();
    res.json(data);
  } catch (error) {
    next(error);
  }
});
