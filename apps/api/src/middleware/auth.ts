import { Request, Response, NextFunction } from "express";
import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { env } from "../config/env.js";

// Extend Express Request type to include user
declare global {
  namespace Express {
    interface Request {
      user?: {
        id: string;
        email?: string;
        emailVerified: boolean;
      };
      supabase?: SupabaseClient;
    }
  }
}

export async function authMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    res.status(401).json({ error: "Missing or invalid authorization header" });
    return;
  }

  const token = authHeader.substring(7);

  // Create a Supabase client with the user's token
  const supabase = createClient(env.SUPABASE_URL, env.SUPABASE_ANON_KEY, {
    global: {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  });

  // Verify the token and get user
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser(token);

  if (error || !user) {
    res.status(401).json({ error: "Invalid or expired token" });
    return;
  }

  // Attach user and authenticated supabase client to request
  req.user = {
    id: user.id,
    email: user.email,
    emailVerified: !!user.email_confirmed_at,
  };
  req.supabase = supabase;

  next();
}

// Requires both authentication AND email verification
export async function verifiedAuthMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    res.status(401).json({ error: "Missing or invalid authorization header" });
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

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser(token);

  if (error || !user) {
    res.status(401).json({ error: "Invalid or expired token" });
    return;
  }

  // Check email verification
  if (!user.email_confirmed_at) {
    res.status(403).json({
      error: "Email not verified",
      code: "EMAIL_NOT_VERIFIED",
      email: user.email,
    });
    return;
  }

  req.user = {
    id: user.id,
    email: user.email,
    emailVerified: true,
  };
  req.supabase = supabase;

  next();
}

// Optional auth - attaches user if present but doesn't require it
export async function optionalAuthMiddleware(
  req: Request,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    next();
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

  const {
    data: { user },
  } = await supabase.auth.getUser(token);

  if (user) {
    req.user = {
      id: user.id,
      email: user.email,
      emailVerified: !!user.email_confirmed_at,
    };
    req.supabase = supabase;
  }

  next();
}
