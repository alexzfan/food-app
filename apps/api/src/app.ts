import express from "express";
import cors from "cors";
import { authRoutes } from "./routes/auth.js";
import { recipeRoutes } from "./routes/recipes.js";
import { youtubeRoutes } from "./routes/youtube.js";
import { favoritesRoutes } from "./routes/favorites.js";
import { profileRoutes } from "./routes/profile.js";
import { audioRoutes } from "./routes/audio.js";

export const app = express();

app.use(cors());
app.use(express.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// Routes
app.use("/api/auth", authRoutes);
app.use("/api/recipes", recipeRoutes);
app.use("/api/youtube", youtubeRoutes);
app.use("/api/favorites", favoritesRoutes);
app.use("/api/profile", profileRoutes);
app.use("/api/audio", audioRoutes);

// Error handler
app.use(
  (
    err: Error,
    _req: express.Request,
    res: express.Response,
    _next: express.NextFunction
  ) => {
    console.error("Error:", err.message);
    res.status(500).json({ error: err.message });
  }
);
