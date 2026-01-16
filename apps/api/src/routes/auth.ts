import { Router } from "express";
import { createClient } from "@supabase/supabase-js";
import { env } from "../config/env.js";

export const authRoutes = Router();

// Admin client for auth operations
const supabaseAdmin = createClient(env.SUPABASE_URL, env.SUPABASE_SERVICE_ROLE_KEY);

// Resend verification email
authRoutes.post("/resend-verification", async (req, res, next) => {
  try {
    const { email } = req.body;

    if (!email) {
      res.status(400).json({ error: "Email is required" });
      return;
    }

    const { error } = await supabaseAdmin.auth.resend({
      type: "signup",
      email,
    });

    if (error) {
      // Don't reveal if email exists or not for security
      if (error.message.includes("rate limit")) {
        res.status(429).json({ error: "Too many requests. Please try again later." });
        return;
      }
      // Return success even if email doesn't exist (security best practice)
    }

    res.json({ message: "If an account exists, a verification email has been sent." });
  } catch (error) {
    next(error);
  }
});

// Check if email is verified (requires auth token)
authRoutes.get("/verification-status", async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;

    if (!authHeader || !authHeader.startsWith("Bearer ")) {
      res.status(401).json({ error: "Missing authorization header" });
      return;
    }

    const token = authHeader.substring(7);

    const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
      global: {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    });

    const { data: { user }, error } = await supabase.auth.getUser(token);

    if (error || !user) {
      res.status(401).json({ error: "Invalid token" });
      return;
    }

    res.json({
      verified: !!user.email_confirmed_at,
      email: user.email,
      confirmedAt: user.email_confirmed_at,
    });
  } catch (error) {
    next(error);
  }
});
