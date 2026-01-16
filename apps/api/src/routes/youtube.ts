import { Router } from "express";
import { searchRecipeVideos, getVideoDetails, getVideoTranscript } from "../services/youtube.js";

export const youtubeRoutes = Router();

// Search YouTube for recipe videos
youtubeRoutes.get("/search", async (req, res, next) => {
  try {
    const query = req.query.q as string;
    const maxResults = parseInt(req.query.maxResults as string) || 10;
    const pageToken = req.query.pageToken as string | undefined;

    if (!query) {
      res.status(400).json({ error: "Query parameter 'q' is required" });
      return;
    }

    const results = await searchRecipeVideos(query, maxResults, pageToken);
    res.json(results);
  } catch (error) {
    next(error);
  }
});

// Get video details
youtubeRoutes.get("/video/:videoId", async (req, res, next) => {
  try {
    const { videoId } = req.params;
    const video = await getVideoDetails(videoId);
    res.json(video);
  } catch (error) {
    next(error);
  }
});

// Get video transcript
youtubeRoutes.get("/video/:videoId/transcript", async (req, res, next) => {
  try {
    const { videoId } = req.params;
    const transcript = await getVideoTranscript(videoId);
    res.json({ videoId, transcript });
  } catch (error) {
    next(error);
  }
});
